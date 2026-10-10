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
        """Under self._lock: add the tokens, add cost(input, output, tier) to usd, count the call."""
        raise NotImplementedError("Part 3: charge one model call to the budget (Budget.charge)")

    @property
    def exhausted(self) -> bool:
        """True once usd >= max_usd or tokens >= max_tokens (a cap of None never trips)."""
        raise NotImplementedError("Part 3: is the budget spent? (Budget.exhausted)")

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
        """If hard and the budget is spent, raise BudgetExceeded(self.budget.summary()).
        Otherwise call self.inner.complete(...), charge resp.usage at self.tier, return resp."""
        raise NotImplementedError("Part 3: check, call, charge (BudgetedModel.complete)")


def run_parallel(sub_questions: list[str], worker: Callable[[str], WorkerResult], budget: Budget | None = None,
                 max_workers: int = 4) -> list[WorkerResult]:
    """Run worker(sub_question) for each sub-question on a ThreadPoolExecutor.

    Results come back in the same order as sub_questions (pool.map keeps order). Errors never
    escape: BudgetExceeded becomes status "budget", any other exception "failed" (put the
    message in .error), and a sub-question whose turn comes after the budget is spent
    becomes "skipped" without calling worker.
    """
    raise NotImplementedError("Part 3: fan workers out on a thread pool (run_parallel)")
