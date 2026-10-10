"""Part 7: 40 conversations, exact checks on routes, tool calls and citations, plus an LLM judge."""
from supportbot.config import EVALS
from supportbot.evals import (build_judge_prompt, check_exact, check_tool_calls, judge, load_evals,
                              parse_judgment, run_suite)
from supportbot.model import MockModel, Model, Response


def test_the_eval_set_has_40_cases_covering_every_route():
    cases = load_evals(EVALS)
    assert len(cases) == 40 and len({c["id"] for c in cases}) == 40
    assert {c["expect"]["route"] for c in cases} == {"refund", "order_status", "product_question", "other"}
    assert sum(bool(c.get("poisoned")) for c in cases) >= 2


def test_tool_calls_must_match_exactly_in_order():
    expected = [{"name": "lookup_order", "args": {"order_id": "NW-1004"}},
                {"name": "issue_refund", "args": {"order_id": "NW-1004", "amount": 49}}]
    good = [{"name": "lookup_order", "input": {"order_id": "NW-1004"}},
            {"name": "issue_refund", "input": {"order_id": "NW-1004", "amount": 49.0, "reason": "anything"}}]
    assert check_tool_calls(expected, good) == []
    assert check_tool_calls(expected, good[::-1])
    assert check_tool_calls(expected, [good[0], {"name": "issue_refund", "input": {"order_id": "NW-1004", "amount": 50}}])
    assert check_tool_calls(expected, good + [{"name": "escalate_to_human", "input": {}}])


def test_blocked_calls_do_not_count():
    blocked = {"name": "issue_refund", "input": {"order_id": "NW-1001"}, "blocked": True}
    assert check_tool_calls([], [blocked]) == []


def test_check_exact_reports_route_and_citations():
    case = {"expect": {"route": "refund", "cites": ["refund-timing"]}}
    problems = check_exact(case, {"route": "other", "tool_calls": [], "citations": []})
    assert len(problems) == 2


def test_judge_prompt_lists_the_rubric():
    _, messages = build_judge_prompt("q?", "an answer", {"must_mention": ["30 days"], "must_not_mention": ["NW-1001"]})
    content = messages[0]["content"]
    assert "ANSWER: an answer" in content and "- must mention: 30 days" in content and "- must not mention: NW-1001" in content


def test_parse_judgment_never_crashes():
    assert parse_judgment('Here you go: {"pass": true, "score": 0.9, "reason": "fine"}')["pass"] is True
    bad = parse_judgment("I think it is good")
    assert bad["pass"] is False and bad["score"] == 0.0


def test_mock_judge_grades_against_the_rubric():
    rubric = {"must_mention": ["30 days"], "must_not_mention": ["60 days"]}
    assert judge("q", "You have 30 days.", rubric, MockModel())["pass"]
    v = judge("q", "You have 60 days.", rubric, MockModel())
    assert not v["pass"] and "30 days" in v["reason"]


def test_a_judge_that_rambles_fails_the_case():
    class Rambles(Model):
        def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
            return Response(text="What a lovely answer.")
    assert not judge("q", "a", {"must_mention": ["x"]}, Rambles())["pass"]


def test_the_reference_bot_passes_all_40():
    report = run_suite(load_evals(EVALS))
    failed = [(r.id, r.exact_problems, r.judgment["reason"]) for r in report["results"] if not r.passed]
    assert report["total"] == 40 and failed == []


def test_a_broken_bot_is_caught():
    """Swap in a model that never calls tools: the exact checks must notice."""
    class NoTools(MockModel):
        def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
            return super().complete(messages, None, system, temperature, max_tokens)
    cases = [c for c in load_evals(EVALS) if c["expect"]["tool_calls"]][:5]
    report = run_suite(cases, model_factory=NoTools)
    assert report["exact_pass_rate"] == 0.0
