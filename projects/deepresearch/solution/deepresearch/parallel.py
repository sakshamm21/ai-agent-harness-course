"""Part 3: run workers in parallel under one shared cost cap.

Every model call goes through a BudgetedModel that charges a shared Budget. When the cap is
hit, new calls raise BudgetExceeded, running workers stop at their next model call, and
workers that have not started are skipped. Whatever finished is kept: a partial answer
beats a crash.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .model import Model, Response
from .records import WorkerResult
from .tokens import cost


class BudgetExceeded(Exception):
    """Raised by a hard BudgetedModel when the shared cap is already spent."""


class Budget:
    """A thread-safe meter of tokens and dollars with optional caps."""

    def __init__(self, max_usd: float | None = None, max_tokens: int | None = None):
        self.max_usd = max_usd
        self.max_tokens = max_tokens
        self.usd = 0.0
        self.tokens = 0
        self.calls = 0
        self._lock = threading.Lock()

    def charge(self, input_tokens: int, output_tokens: int, tier: str = "medium") -> None:
        with self._lock:
            self.tokens += input_tokens + output_tokens
            self.usd += cost(input_tokens, output_tokens, tier)
            self.calls += 1

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return ((self.max_usd is not None and self.usd >= self.max_usd)
                    or (self.max_tokens is not None and self.tokens >= self.max_tokens))

    def summary(self) -> str:
        cap = []
        if self.max_usd is not None:
            cap.append(f"${self.max_usd:.4f}")
        if self.max_tokens is not None:
            cap.append(f"{self.max_tokens:,} tokens")
        return f"{self.calls} calls, {self.tokens:,} tokens, ${self.usd:.4f}" + (f" (cap {', '.join(cap)})" if cap else "")


class BudgetedModel(Model):
    """Wraps a model so every call is charged to a Budget.

    hard=True refuses new calls once the budget is spent (use it for workers).
    hard=False only records spend (use it for the planner and writer, so a report always comes out).
    """

    def __init__(self, inner: Model, budget: Budget, hard: bool = True):
        self.inner = inner
        self.budget = budget
        self.hard = hard
        self.name = inner.name
        self.tier = inner.tier

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1500) -> Response:
        if self.hard and self.budget.exhausted:
            raise BudgetExceeded(self.budget.summary())
        resp = self.inner.complete(messages, tools=tools, system=system, temperature=temperature,
                                   max_tokens=max_tokens)
        self.budget.charge(resp.usage.input_tokens, resp.usage.output_tokens, self.tier)
        return resp


def run_parallel(sub_questions: list[str], worker: Callable[[str], WorkerResult], budget: Budget | None = None,
                 max_workers: int = 4) -> list[WorkerResult]:
    """Run worker(sub_question) for each sub-question on a thread pool.

    Results come back in the same order as sub_questions. Errors never escape:
    BudgetExceeded becomes status "budget", any other exception "failed", and a
    sub-question that would start after the budget ran out becomes "skipped".
    """

    def one(q: str) -> WorkerResult:
        if budget is not None and budget.exhausted:
            return WorkerResult(q, "skipped", error="budget spent before this worker started")
        try:
            return worker(q)
        except BudgetExceeded as e:
            return WorkerResult(q, "budget", error=f"stopped by cost cap: {e}")
        except Exception as e:  # one broken worker must not sink the others
            return WorkerResult(q, "failed", error=f"{type(e).__name__}: {e}")

    if not sub_questions:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(sub_questions)))) as pool:
        return list(pool.map(one, sub_questions))
