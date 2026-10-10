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
    """A JSON array of strings from the model, cleaned: stripped, deduplicated, capped.

    1. data = extract_json(text). If it is a dict, use its first list value.
    2. Not a list? Return [].
    3. Strip each item, skip empties, drop case-insensitive duplicates (keep the first).
    4. Return at most max_subquestions.
    """
    raise NotImplementedError("Part 1: parse the planner's JSON array (parse_plan)")


def plan(question: str, model: Model, max_subquestions: int = 4) -> list[str]:
    """Ask the planner for sub-questions. Falls back to [question] if the plan is unusable.

    One model.complete call: user message plan_prompt(...), system=PLANNER_SYSTEM.
    """
    raise NotImplementedError("Part 1: ask the planner model for sub-questions (plan)")


def replan(question: str, failed: list[str], answered: list[str], model: Model,
           max_subquestions: int = 4) -> list[str]:
    """Replacement sub-questions for the failed ones. Never repeats a failed one word for word.

    No failures: return [] without calling the model. Otherwise one call with
    replan_prompt(...) and REPLANNER_SYSTEM, parsed with parse_plan, minus anything
    already in failed or answered (case-insensitive).
    """
    raise NotImplementedError("Part 1: write replacement sub-questions (replan)")


def orchestrate(question: str, model: Model, run_workers: Callable[[list[str]], list[WorkerResult]],
                max_subquestions: int = 4, max_replans: int = 1,
                on_event: Callable[[dict], None] | None = None) -> tuple[list[str], list[WorkerResult]]:
    """Plan, run the workers, replan failures up to max_replans times.

    Returns (every sub-question asked, final results). A failed result that was replaced
    is dropped; a failed result with no replacement stays, so the writer can list it as a gap.

    1. subs = plan(...); results = run_workers(subs).
    2. Up to max_replans times: failed = results with status in REPLAN_STATUSES.
       None? stop. Else replan them; no replacements? stop.
       Else results = the non-failed results + run_workers(replacements).
    3. Call on_event({"type": "plan", ...}) / ({"type": "replan", ...}) if given (optional).
    """
    raise NotImplementedError("Part 1: plan, run workers, replan failures (orchestrate)")
