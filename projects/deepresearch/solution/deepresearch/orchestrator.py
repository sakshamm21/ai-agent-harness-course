"""Part 1: the orchestrator. Plan sub-questions, hand them out, replan the ones that fail.

The orchestrator never searches. It decides what to research and reads what comes back,
which keeps its own context small no matter how many pages the workers read.
"""
from __future__ import annotations

from typing import Callable

from .model import Model
from .prompts import PLANNER_SYSTEM, REPLANNER_SYSTEM, plan_prompt, replan_prompt
from .records import WorkerResult
from .textutil import extract_json

# A worker that came back "failed" or "empty" is worth another try with new wording.
# "budget" and "skipped" mean the money ran out; asking again would only spend more.
REPLAN_STATUSES = {"failed", "empty"}


def parse_plan(text: str, max_subquestions: int) -> list[str]:
    """A JSON array of strings from the model, cleaned: stripped, deduplicated, capped."""
    data = extract_json(text)
    if isinstance(data, dict):  # tolerate {"sub_questions": [...]}
        data = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(data, list):
        return []
    seen: dict[str, str] = {}
    for item in data:
        q = str(item).strip() if isinstance(item, (str, int, float)) else ""
        if q and q.lower() not in seen:
            seen[q.lower()] = q
    return list(seen.values())[:max_subquestions]


def plan(question: str, model: Model, max_subquestions: int = 4) -> list[str]:
    """Ask the planner for sub-questions. Falls back to the question itself if the plan is unusable."""
    resp = model.complete([{"role": "user", "content": plan_prompt(question, max_subquestions)}],
                          system=PLANNER_SYSTEM)
    return parse_plan(resp.text, max_subquestions) or [question]


def replan(question: str, failed: list[str], answered: list[str], model: Model,
           max_subquestions: int = 4) -> list[str]:
    """Replacement sub-questions for the failed ones. Never repeats a failed one word for word."""
    if not failed:
        return []
    resp = model.complete([{"role": "user", "content": replan_prompt(question, failed, answered, max_subquestions)}],
                          system=REPLANNER_SYSTEM)
    old = {q.lower() for q in failed + answered}
    return [q for q in parse_plan(resp.text, max_subquestions) if q.lower() not in old]


def orchestrate(question: str, model: Model, run_workers: Callable[[list[str]], list[WorkerResult]],
                max_subquestions: int = 4, max_replans: int = 1,
                on_event: Callable[[dict], None] | None = None) -> tuple[list[str], list[WorkerResult]]:
    """Plan, run the workers, replan failures up to max_replans times.

    Returns (every sub-question asked, final results). A failed result that was replaced
    is dropped; a failed result with no replacement stays, so the writer can list it as a gap.
    """
    emit = on_event or (lambda e: None)
    subs = plan(question, model, max_subquestions)
    emit({"type": "plan", "sub_questions": subs})
    asked = list(subs)
    results = run_workers(subs)
    for _ in range(max_replans):
        failed = [r for r in results if r.status in REPLAN_STATUSES]
        if not failed:
            break
        answered = [r.sub_question for r in results if r.ok]
        new = replan(question, [r.sub_question for r in failed], answered, model, len(failed))
        emit({"type": "replan", "failed": [r.sub_question for r in failed], "new": new})
        if not new:
            break
        asked += new
        results = [r for r in results if r.status not in REPLAN_STATUSES] + run_workers(new)
    return asked, results
