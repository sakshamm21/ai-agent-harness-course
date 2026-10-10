"""Part 1: the orchestrator plans sub-questions and replans the ones that fail."""
from deepresearch.model import MockModel, ResearchMock, Response
from deepresearch.orchestrator import orchestrate, parse_plan, plan, replan
from deepresearch.records import Claim, WorkerResult

Q1 = "When did the Velmora Tunnel open? How long is it? How much did it cost?"


def test_parse_plan_reads_a_json_array():
    assert parse_plan('["A?", "B?"]', 4) == ["A?", "B?"]


def test_parse_plan_tolerates_fences_chatter_and_objects():
    assert parse_plan('Here you go:\n```json\n["A?", "B?"]\n```', 4) == ["A?", "B?"]
    assert parse_plan('{"sub_questions": ["A?"]}', 4) == ["A?"]


def test_parse_plan_dedupes_strips_and_caps():
    assert parse_plan('[" A? ", "a?", "B?", "", "C?", "D?", "E?"]', 3) == ["A?", "B?", "C?"]


def test_parse_plan_returns_empty_for_garbage():
    assert parse_plan("I think you should look it up.", 4) == []


def test_plan_splits_a_compound_question_into_standalone_parts():
    subs = plan(Q1, ResearchMock(), max_subquestions=4)
    assert len(subs) == 3
    assert all("Velmora" in s for s in subs), "each sub-question must name its subject, never just 'it'"


def test_plan_respects_max_subquestions():
    assert len(plan(Q1, ResearchMock(), max_subquestions=2)) == 2


def test_plan_falls_back_to_the_question_when_the_plan_is_unusable():
    junk = MockModel([Response(text="Sorry, I can't do that.")])
    assert plan("What is X?", junk) == ["What is X?"]


def test_replan_writes_new_wording_for_failed_sub_questions():
    failed = ["How long is it (Velmora Tunnel)?"]
    new = replan(Q1, failed, ["When did the Velmora Tunnel open?"], ResearchMock())
    assert new and all(n.lower() not in {f.lower() for f in failed} for n in new)


def test_replan_never_repeats_a_failed_question_verbatim():
    parrot = MockModel([Response(text='["Q one?", "Q two?"]')])
    assert replan("Q", ["Q one?"], [], parrot) == ["Q two?"]


def test_replan_with_nothing_failed_makes_no_call():
    m = MockModel([Response(text='["x"]')])
    assert replan("Q", [], ["a"], m) == [] and m.calls == 0


def _fake_workers(fail: set[str], status: str = "failed"):
    calls = []

    def run(qs):
        calls.append(list(qs))
        out = []
        for q in qs:
            if q in fail:
                out.append(WorkerResult(q, status, error="boom"))
            else:
                out.append(WorkerResult(q, "ok", [Claim(f"fact about {q}", ["vt-01"])], ["vt-01"]))
        return out
    return run, calls


def test_orchestrate_runs_every_planned_sub_question():
    run, calls = _fake_workers(set())
    asked, results = orchestrate(Q1, ResearchMock(), run)
    assert len(calls) == 1 and calls[0] == asked
    assert [r.status for r in results] == ["ok", "ok", "ok"]


def test_orchestrate_replans_when_a_worker_fails():
    subs = plan(Q1, ResearchMock())
    run, calls = _fake_workers({subs[1]})
    asked, results = orchestrate(Q1, ResearchMock(), run)
    assert len(calls) == 2, "a failed worker should trigger one replan round"
    assert len(calls[1]) == 1 and calls[1][0] != subs[1]
    assert calls[1][0] in asked
    assert all(r.ok for r in results), "the failed result is replaced by the replanned one"
    assert subs[1] not in [r.sub_question for r in results]


def test_orchestrate_also_replans_empty_results():
    subs = plan(Q1, ResearchMock())
    run, calls = _fake_workers({subs[0]}, status="empty")
    orchestrate(Q1, ResearchMock(), run)
    assert len(calls) == 2


def test_orchestrate_does_not_replan_budget_stops():
    subs = plan(Q1, ResearchMock())
    run, calls = _fake_workers({subs[0]}, status="budget")
    _, results = orchestrate(Q1, ResearchMock(), run)
    assert len(calls) == 1, "out of money is not a reason to spend more"
    assert results[0].status == "budget"


def test_orchestrate_keeps_failures_when_replans_are_used_up():
    run, calls = _fake_workers({s for s in plan(Q1, ResearchMock())} | {"long velmora tunnel"})
    _, results = orchestrate(Q1, ResearchMock(), run, max_replans=0)
    assert len(calls) == 1 and all(r.status == "failed" for r in results)
