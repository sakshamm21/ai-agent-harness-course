"""research(): the whole pipeline, wired from the six parts.

    plan (1) -> parallel workers with search/fetch (2, 3) -> verify citations (4) -> write (5)

This file has no logic of its own worth testing; the parts do the work.
"""
from __future__ import annotations

from typing import Callable

from .corpus import Corpus
from .model import Model, get_models
from .orchestrator import orchestrate
from .parallel import Budget, BudgetedModel, run_parallel
from .records import ResearchResult, WorkerResult
from .verifier import verify_and_revise
from .worker import run_worker
from .writer import write_report


def research(question: str, models: dict[str, Model] | None = None, corpus: Corpus | None = None,
             max_usd: float | None = 0.50, max_tokens: int | None = None, max_workers: int = 4,
             max_subquestions: int = 4, verify: bool = True, verify_rounds: int = 2,
             on_event: Callable[[dict], None] | None = None) -> ResearchResult:
    models = models or get_models()
    corpus = corpus or Corpus.load()
    emit = on_event or (lambda e: None)
    budget = Budget(max_usd=max_usd, max_tokens=max_tokens)
    # Workers are hard-capped. The planner, verifier and writer are metered but never refused,
    # so a run that hits the cap still verifies what it has and writes a (partial) report.
    worker_model = BudgetedModel(models["worker"], budget, hard=True)
    soft = {r: BudgetedModel(models[r], budget, hard=False) for r in ("planner", "verifier", "reviser", "writer")}
    verify_reports = []

    def one(q: str) -> WorkerResult:
        r = run_worker(q, worker_model, corpus)
        emit({"type": "worker", "sub_question": q, "status": r.status, "claims": len(r.claims)})
        if verify and r.ok:
            r, rep = verify_and_revise(r, corpus, soft["verifier"], soft["reviser"], verify_rounds)
            verify_reports.append(rep)
            emit({"type": "verify", "sub_question": q, "failures_per_round": rep.failures_per_round})
        return r

    def run_workers(qs: list[str]) -> list[WorkerResult]:
        return run_parallel(qs, one, budget, max_workers)

    subs, results = orchestrate(question, soft["planner"], run_workers, max_subquestions, on_event=emit)
    partial = any(r.status in ("budget", "skipped") for r in results)
    report = write_report(question, results, soft["writer"], corpus, partial=partial)
    return ResearchResult(question, report, subs, results, partial, round(budget.usd, 6), budget.tokens,
                          verify_reports)
