"""Part 4: route with a small model, fall back to rules, and run the agent loop with the route's tools."""
import pytest

from supportbot.agent import SupportAgent, history_append
from supportbot.model import MockModel, Model, Response
from supportbot.router import TOOLS_BY_ROUTE, parse_label, route, routing_text, rule_route


class Says(Model):
    def __init__(self, text):
        self.text = text

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
        return Response(text=self.text)


@pytest.mark.parametrize("message, label", [
    ("I want a refund for NW-1004", "refund"),
    ("Where is my order NW-1003?", "order_status"),
    ("Do you ship to Canada?", "product_question"),
    ("How long do refunds take?", "product_question"),
    ("I want to speak to a human", "other"),
    ("Tell me a joke", "other"),
])
def test_router_model_labels(message, label):
    r = route(message, MockModel())
    assert (r.label, r.source) == (label, "model")


@pytest.mark.parametrize("raw, label", [("refund", "refund"), (" Order status.", "order_status"),
                                        ("PRODUCT_QUESTION", "product_question"),
                                        ("I think this is a refund", None), ("", None)])
def test_parse_label_is_strict(raw, label):
    assert parse_label(raw) == label


def test_bad_model_output_falls_back_to_rules():
    r = route("Where is my package NW-1010?", Says("Sure! Happy to help with that."))
    assert (r.label, r.source) == ("order_status", "rules")


def test_rules_without_a_model():
    assert rule_route("refund please NW-1001") == "refund"
    assert rule_route("hello") == "other"


def test_short_follow_up_is_routed_with_the_previous_message():
    assert routing_text("NW-1015", ["I want a refund"]) == "I want a refund\nNW-1015"
    assert routing_text("Do you ship to Canada?", ["hi"]) == "Do you ship to Canada?"


def test_each_route_sees_only_its_tools():
    assert "issue_refund" in TOOLS_BY_ROUTE["refund"]
    assert all("issue_refund" not in TOOLS_BY_ROUTE[r] for r in ("order_status", "product_question", "other"))


def _agent(index, store):
    return SupportAgent(index, store, model=MockModel(), guardrails=False, trust_boundary=False)


def test_order_status_looks_the_order_up(index, store):
    r = _agent(index, store).handle("Where is my order NW-1003?")
    assert r.route == "order_status" and [c["name"] for c in r.tool_calls] == ["lookup_order"]
    assert "FedEx" in r.text


def test_refund_runs_lookup_then_refund(index, store):
    r = _agent(index, store).handle("I'd like a refund for order NW-1004")
    assert [c["name"] for c in r.tool_calls] == ["lookup_order", "issue_refund"]
    assert store.order("NW-1004")["refunded_amount"] == 49.0


def test_product_question_cites_and_calls_no_tools(index, store):
    r = _agent(index, store).handle("Do gift cards expire?")
    assert r.route == "product_question" and r.tool_calls == [] and r.citations == ["gift-cards"]


def test_tools_the_route_does_not_offer_are_refused(index, store):
    class Rogue(Model):            # always tries to refund, whatever the route
        def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
            if any(isinstance(m["content"], list) and m["content"][0].get("type") == "tool_result" for m in messages):
                return Response(text="ok")
            from supportbot.model import ToolCall
            return Response(tool_calls=[ToolCall("t1", "issue_refund", {"order_id": "NW-1001", "amount": 5, "reason": "x"})])
    agent = SupportAgent(index, store, model=Rogue(), router_model=MockModel(), guardrails=False, trust_boundary=False)
    r = agent.handle("Do gift cards expire?")
    assert r.tool_calls[0]["blocked"] and store.rows("refunds") == []


def test_the_loop_stops_at_max_turns(index, store):
    class Loops(Model):
        def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
            from supportbot.model import ToolCall
            return Response(tool_calls=[ToolCall(f"t{len(messages)}", "lookup_order", {"order_id": "NW-1001"})])
    agent = SupportAgent(index, store, model=Loops(), router_model=MockModel(), max_turns=3,
                         guardrails=False, trust_boundary=False)
    r = agent.handle("Where is NW-1001?")
    assert len(r.tool_calls) == 3 and any(e["type"] == "max_turns" for e in r.events)


def test_multi_turn_conversation(index, store):
    agent = _agent(index, store)
    first = agent.handle("Where is my package?")
    assert "order number" in first.text and first.tool_calls == []
    second = agent.handle("It's NW-1010", history_append([], "Where is my package?", first))
    assert second.route == "order_status" and second.tool_calls[0]["input"]["order_id"] == "NW-1010"


def test_events_tell_the_story(index, store):
    r = _agent(index, store).handle("Where is my order NW-1003?")
    types = [e["type"] for e in r.events]
    assert types[:3] == ["user_message", "route", "retrieve"] and types[-1] == "final"
    assert "tool_call" in types and all(e["conversation_id"] == r.conversation_id for e in r.events)
