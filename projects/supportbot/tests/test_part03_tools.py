"""Part 3: lookup_order, issue_refund (idempotent), escalate_to_human, and run_tool."""
import json

import pytest

from supportbot.tools import (ToolError, escalate_to_human, issue_refund, lookup_order, make_idempotency_key,
                              run_tool)


def test_store_is_seeded_with_30_orders(store):
    assert len(store.rows("orders")) == 30


def test_lookup_order_returns_the_order(store):
    o = lookup_order(store, "nw-1003 ")
    assert o["order_id"] == "NW-1003" and o["status"] == "shipped" and o["items"][0]["name"] == "Ridge Fleece"


@pytest.mark.parametrize("bad, words", [("1003", "NW-1234"), ("NW-9999", "No order")])
def test_lookup_order_errors_say_what_to_do(store, bad, words):
    with pytest.raises(ToolError, match=words):
        lookup_order(store, bad)


def test_issue_refund_writes_both_tables(store):
    r = issue_refund(store, "NW-1004", 49.0, "too small", "key-1")
    assert r["status"] == "refunded" and r["amount"] == 49.0 and r["duplicate"] is False
    assert store.order("NW-1004")["refunded_amount"] == 49.0 and len(store.rows("refunds")) == 1


def test_same_idempotency_key_refunds_once(store):
    first = issue_refund(store, "NW-1004", 20.0, "x", "key-1")
    again = issue_refund(store, "NW-1004", 20.0, "x", "key-1")
    assert again["duplicate"] is True and again["refund_id"] == first["refund_id"]
    assert len(store.rows("refunds")) == 1 and store.order("NW-1004")["refunded_amount"] == 20.0


def test_reusing_a_key_for_a_different_refund_is_an_error(store):
    issue_refund(store, "NW-1004", 20.0, "x", "key-1")
    with pytest.raises(ToolError, match="different refund"):
        issue_refund(store, "NW-1004", 25.0, "x", "key-1")


@pytest.mark.parametrize("order_id, amount, words", [
    ("NW-1003", 10, "shipped"),            # not delivered yet
    ("NW-1006", 10, "cancelled instead"),  # processing: cancel, do not refund
    ("NW-1001", 500, "more than"),         # more than the order total
    ("NW-1001", 0, "more than \\$0"),
])
def test_refund_rules(store, order_id, amount, words):
    with pytest.raises(ToolError, match=words):
        issue_refund(store, order_id, amount, "x", f"k-{order_id}-{amount}")
    assert store.rows("refunds") == []


def test_cannot_refund_more_than_is_left(store):
    issue_refund(store, "NW-1001", 60, "x", "a")
    with pytest.raises(ToolError, match="29.00 left"):
        issue_refund(store, "NW-1001", 30, "x", "b")


def test_escalate_opens_a_ticket(store):
    t = escalate_to_human(store, "Customer wants a manager", "complaint", "NW-1007")
    assert t["ticket_id"] == "ESC-0001" and store.rows("tickets")[0]["order_id"] == "NW-1007"
    with pytest.raises(ToolError):
        escalate_to_human(store, "  ", "complaint")


def test_idempotency_key_is_stable_per_conversation():
    k = make_idempotency_key("c1", "issue_refund", {"order_id": "NW-1004", "amount": 49.0})
    assert k == make_idempotency_key("c1", "issue_refund", {"amount": 49.0, "order_id": "NW-1004"})
    assert k != make_idempotency_key("c2", "issue_refund", {"order_id": "NW-1004", "amount": 49.0})


def test_run_tool_returns_json_the_model_can_read(store):
    r = run_tool(store, "lookup_order", {"order_id": "NW-1001"})
    assert not r.is_error and json.loads(r.content)["total"] == 89.0


def test_run_tool_turns_problems_into_error_results(store):
    assert run_tool(store, "delete_everything", {}).is_error
    assert "missing required argument 'reason'" in run_tool(store, "issue_refund", {"order_id": "NW-1001", "amount": 5}).content
    assert run_tool(store, "issue_refund", {"order_id": "NW-1001", "amount": "lots", "reason": "x"}).is_error
    assert run_tool(store, "lookup_order", {"order_id": "NW-0000"}).content.startswith("Error:")


def test_a_retried_tool_call_does_not_refund_twice(store):
    args = {"order_id": "NW-1004", "amount": 49, "reason": "retry"}
    first = run_tool(store, "issue_refund", args, conversation_id="conv-1")
    again = run_tool(store, "issue_refund", args, conversation_id="conv-1")
    assert not first.is_error and json.loads(again.content)["duplicate"] is True
    assert len(store.rows("refunds")) == 1


def test_refund_gate_can_replace_the_refund(store):
    gate = lambda store, args, key: {"status": "held", "key": key}   # noqa: E731
    r = run_tool(store, "issue_refund", {"order_id": "NW-1004", "amount": 49, "reason": "x"}, refund_gate=gate)
    assert r.data["status"] == "held" and store.rows("refunds") == []
