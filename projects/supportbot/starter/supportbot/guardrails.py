"""Part 5: guardrails in code, not in the prompt.

1. PII redaction on everything the bot says (and everything the tracer writes).
2. Refunds over $100 wait for a human: the tool call becomes an approval request.
"""
from __future__ import annotations

import re

from .config import REFUND_APPROVAL_LIMIT
from .tools import OrderStore, ToolError, check_refundable, issue_refund, now

# Order matters: cards before phones, so a card number is not half-eaten by the phone pattern.
PII_PATTERNS = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), "[email]"),
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[card number]"),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    ("phone", re.compile(r"(?:\+1[\s.-]?)?(?:\(\d{3}\)\s?|\b\d{3}[\s.-])\d{3}[\s.-]\d{4}\b"), "[phone]"),
]


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace emails, card numbers, SSNs and phone numbers. Returns (text, counts by kind).

    Card last-4 ("ending in 5037"), order numbers and tracking numbers are not PII here and stay.
    """
    raise NotImplementedError("Part 5: redact PII (redact_pii)")


def redact_value(value):
    """redact_pii applied to every string inside a JSON-like value (for traces)."""
    if isinstance(value, str):
        return redact_pii(value)[0]
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    return value


def needs_approval(amount: float, limit: float = REFUND_APPROVAL_LIMIT) -> bool:
    """Strictly over the limit: a $100.00 refund goes straight through."""
    raise NotImplementedError("Part 5: the approval threshold (needs_approval)")


def refund_gate(store: OrderStore, args: dict, key: str) -> dict | None:
    """Plug into run_tool(refund_gate=...). None lets the refund through; a dict replaces it.

    Over the limit: check the refund is valid at all, then queue it for a person.
    The same key again returns the same pending request (idempotent, like issue_refund).
    """
    raise NotImplementedError("Part 5: hold big refunds for a person (refund_gate)")


def pending_approvals(store: OrderStore) -> list[dict]:
    return [r for r in store.rows("approvals") if r["status"] == "pending"]


def approve_refund(store: OrderStore, approval_id: str, approver: str) -> dict:
    """A person said yes: issue the refund with the request's own idempotency key.

    Unknown id or a rejected request: ToolError. Approving twice is safe: issue_refund sees the
    same key and returns the first refund. Mark the row approved, with decided_by and refund_id.
    """
    raise NotImplementedError("Part 5: issue an approved refund (approve_refund)")


def reject_refund(store: OrderStore, approval_id: str, approver: str) -> dict:
    row = store.db.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
    if row is None:
        raise ToolError(f"No approval request {approval_id}.")
    if row["status"] == "approved":
        raise ToolError(f"{approval_id} was already approved.")
    with store.db:
        store.db.execute("UPDATE approvals SET status = 'rejected', decided_by = ? WHERE approval_id = ?",
                         (approver, approval_id))
    return {"approval_id": approval_id, "status": "rejected"}
