"""Part 3: parallel workers under one shared token/$ cap, stopping gracefully."""
import threading

import pytest

from deepresearch.model import MockModel, ResearchMock, Response
from deepresearch.parallel import Budget, BudgetedModel, BudgetExceeded, run_parallel
from deepresearch.records import WorkerResult
from deepresearch.research import research

Q1 = "When did the Velmora Tunnel open? How long is it? How much did it cost?"


def test_budget_meters_tokens_and_dollars():
    b = Budget(max_usd=1.0)
    b.charge(1_000_000, 0, "medium")
    assert b.tokens == 1_000_000 and b.usd == pytest.approx(3.0)
    assert b.exhausted


def test_budget_token_cap():
    b = Budget(max_tokens=100)
    b.charge(60, 30)
    assert not b.exhausted
    b.charge(10, 0)
    assert b.exhausted


def test_budget_is_thread_safe():
    b = Budget()
    threads = [threading.Thread(target=lambda: [b.charge(1, 1, "small") for _ in range(1000)]) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert b.tokens == 16_000 and b.calls == 8000


def test_hard_budgeted_model_refuses_calls_once_spent():
    b = Budget(max_tokens=1)
    m = BudgetedModel(MockModel([Response(text="hi")]), b, hard=True)
    m.complete([{"role": "user", "content": "hello"}])
    assert b.exhausted
    with pytest.raises(BudgetExceeded):
        m.complete([{"role": "user", "content": "again"}])


def test_soft_budgeted_model_only_records():
    b = Budget(max_tokens=1)
    m = BudgetedModel(MockModel([Response(text="hi")]), b, hard=False)
    m.complete([{"role": "user", "content": "hello"}])
    m.complete([{"role": "user", "content": "again"}])
    assert b.calls == 2


def test_run_parallel_runs_workers_at_the_same_time_and_keeps_order():
    barrier = threading.Barrier(3, timeout=5)  # only passes if 3 workers run at once

    def w(q):
        barrier.wait()
        return WorkerResult(q)
    out = run_parallel(["a", "b", "c"], w, max_workers=3)
    assert [r.sub_question for r in out] == ["a", "b", "c"]
    assert all(r.status == "ok" for r in out), [r.error for r in out]


def test_one_crashing_worker_does_not_sink_the_rest():
    def w(q):
        if q == "bad":
            raise ValueError("network down")
        return WorkerResult(q)
    out = run_parallel(["ok1", "bad", "ok2"], w)
    assert [r.status for r in out] == ["ok", "failed", "ok"]
    assert "network down" in out[1].error


def test_budget_stop_and_skip_statuses():
    b = Budget(max_tokens=10)

    def w(q):
        b.charge(20, 0)
        raise BudgetExceeded("spent")
    out = run_parallel(["a", "b", "c"], w, budget=b, max_workers=1)
    assert out[0].status == "budget"
    assert [r.status for r in out[1:]] == ["skipped", "skipped"]


def test_research_stops_gracefully_at_the_cost_cap(corpus, models):
    res = research(Q1, models=models, corpus=corpus, max_usd=0.003, max_workers=1)
    assert res.partial
    assert any(r.status in ("budget", "skipped") for r in res.results)
    assert res.report.startswith("# ") and "Partial report" in res.report
    assert res.cost_usd < 0.02, "the cap must stop the fan-out, not just note it"


def test_research_with_room_in_the_budget_answers_everything(corpus, models):
    res = research(Q1, models=models, corpus=corpus, max_usd=1.0, max_workers=3)
    assert not res.partial
    assert [r.status for r in res.results] == ["ok", "ok", "ok"]
    assert 0 < res.cost_usd < 1.0 and res.tokens > 0
