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
    counts: dict[str, int] = {}
    for kind, pattern, replacement in PII_PATTERNS:
        text, n = pattern.subn(replacement, text)
        if n:
            counts[kind] = n
    return text, counts


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
    return round(float(amount), 2) > limit


def refund_gate(store: OrderStore, args: dict, key: str) -> dict | None:
    """Plug into run_tool(refund_gate=...). None lets the refund through; a dict replaces it.

    Over the limit: check the refund is valid at all, then queue it for a person.
    The same key again returns the same pending request (idempotent, like issue_refund).
    """
    if not needs_approval(args["amount"]):
        return None
    order, amount, _ = check_refundable(store, args["order_id"], args["amount"])
    row = store.db.execute("SELECT * FROM approvals WHERE idempotency_key = ?", (key,)).fetchone()
    if row is None:
        with store.db:
            approval_id = store.next_id("approvals", "AP")
            store.db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?)",
                             (approval_id, order["order_id"], amount, args.get("reason", ""), key,
                              "pending", None, None, now()))
        row = store.db.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
    return {"status": "pending_approval", "approval_id": row["approval_id"], "order_id": row["order_id"],
            "amount": row["amount"], "message": f"Refunds over ${REFUND_APPROVAL_LIMIT:.0f} need a person to approve."}


def pending_approvals(store: OrderStore) -> list[dict]:
    return [r for r in store.rows("approvals") if r["status"] == "pending"]


def approve_refund(store: OrderStore, approval_id: str, approver: str) -> dict:
    """A person said yes: issue the refund with the request's own idempotency key.

    Unknown id or a rejected request: ToolError. Approving twice is safe: issue_refund sees the
    same key and returns the first refund. Mark the row approved, with decided_by and refund_id.
    """
    row = store.db.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
    if row is None:
        raise ToolError(f"No approval request {approval_id}.")
    if row["status"] == "rejected":
        raise ToolError(f"{approval_id} was rejected by {row['decided_by']}.")
    refund = issue_refund(store, row["order_id"], row["amount"], row["reason"], row["idempotency_key"])
    with store.db:
        store.db.execute("UPDATE approvals SET status = 'approved', decided_by = COALESCE(decided_by, ?), "
                         "refund_id = ? WHERE approval_id = ?", (approver, refund["refund_id"], approval_id))
    return refund


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
