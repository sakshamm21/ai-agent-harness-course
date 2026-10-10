"""Part 5: PII redaction on output, and refunds over $100 wait for a person."""
import pytest

from supportbot.agent import SupportAgent
from supportbot.guardrails import (approve_refund, needs_approval, pending_approvals, redact_pii, refund_gate,
                                   reject_refund)
from supportbot.model import MockModel
from supportbot.tools import ToolError, run_tool


@pytest.mark.parametrize("text, kind, gone", [
    ("Mail me at ava.thompson@example.com please", "email", "ava.thompson@example.com"),
    ("Call (206) 555-0147 after 5", "phone", "555-0147"),
    ("or 206-555-0147", "phone", "555-0147"),
    ("Card 4111 1111 1111 1111 exp 04/29", "card", "4111 1111"),
    ("SSN 123-45-6789", "ssn", "123-45-6789"),
])
def test_redact_pii(text, kind, gone):
    out, counts = redact_pii(text)
    assert gone not in out and counts.get(kind) == 1


def test_redaction_keeps_what_is_not_pii():
    text = "Order NW-1003, tracking 771242757, card ending in 5037, total $93.00 on 2026-09-03."
    assert redact_pii(text) == (text, {})


def test_approval_threshold_is_strictly_over_100():
    assert not needs_approval(100) and not needs_approval(99.99) and needs_approval(100.01)


def test_small_refund_passes_the_gate(store):
    assert refund_gate(store, {"order_id": "NW-1004", "amount": 49.0, "reason": "x"}, "k") is None


def test_large_refund_becomes_an_approval_request(store):
    r = run_tool(store, "issue_refund", {"order_id": "NW-1002", "amount": 149, "reason": "leaks"},
                 conversation_id="c1", refund_gate=refund_gate)
    assert r.data["status"] == "pending_approval" and store.rows("refunds") == []
    assert [a["order_id"] for a in pending_approvals(store)] == ["NW-1002"]


def test_the_gate_is_idempotent_too(store):
    args = {"order_id": "NW-1002", "amount": 149, "reason": "leaks"}
    a = run_tool(store, "issue_refund", args, "c1", refund_gate=refund_gate)
    b = run_tool(store, "issue_refund", args, "c1", refund_gate=refund_gate)
    assert a.data["approval_id"] == b.data["approval_id"] and len(store.rows("approvals")) == 1


def test_the_gate_still_checks_the_refund_is_valid(store):
    r = run_tool(store, "issue_refund", {"order_id": "NW-1019", "amount": 328, "reason": "x"}, refund_gate=refund_gate)
    assert r.is_error and "shipped" in r.content and store.rows("approvals") == []


def test_approving_issues_the_refund_once(store):
    r = run_tool(store, "issue_refund", {"order_id": "NW-1002", "amount": 149, "reason": "x"}, refund_gate=refund_gate)
    aid = r.data["approval_id"]
    first = approve_refund(store, aid, "sam")
    again = approve_refund(store, aid, "sam")
    assert first["amount"] == 149 and again["duplicate"] is True and len(store.rows("refunds")) == 1
    assert store.rows("approvals")[0]["status"] == "approved" and pending_approvals(store) == []


def test_rejected_requests_cannot_be_approved(store):
    r = run_tool(store, "issue_refund", {"order_id": "NW-1002", "amount": 149, "reason": "x"}, refund_gate=refund_gate)
    reject_refund(store, r.data["approval_id"], "sam")
    with pytest.raises(ToolError, match="rejected"):
        approve_refund(store, r.data["approval_id"], "sam")
    assert store.rows("refunds") == []


def test_agent_sends_big_refunds_for_approval(index, store):
    r = SupportAgent(index, store, model=MockModel()).handle("Please refund NW-1002, the jacket leaks")
    assert "approval" in r.text and store.rows("refunds") == [] and len(pending_approvals(store)) == 1


def test_agent_output_is_redacted(index, store):
    r = SupportAgent(index, store, model=MockModel()).handle("Where is my order NW-1003?")
    assert "sofia.garcia@example.com" not in r.text and "[email]" in r.text
    assert any(e["type"] == "redacted" for e in r.events)


def test_without_guardrails_the_same_reply_leaks(index, store):
    r = SupportAgent(index, store, model=MockModel(), guardrails=False).handle("Where is my order NW-1003?")
    assert "sofia.garcia@example.com" in r.text
