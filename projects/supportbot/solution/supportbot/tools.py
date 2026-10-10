"""Part 3: tools backed by a fake store in SQLite.

lookup_order, issue_refund (idempotent) and escalate_to_human, plus run_tool, the one
place the agent goes through to call any of them. Errors come back as text the model
can act on, never as a crash.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ORDER_ID_RE = re.compile(r"^NW-\d{4}$")
REFUNDABLE_STATUSES = ("delivered", "refunded")

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY, customer_name TEXT, email TEXT, phone TEXT, card_last4 TEXT,
  items TEXT, total REAL, status TEXT, placed_at TEXT, carrier TEXT, tracking TEXT, eta TEXT,
  delivered_at TEXT, refunded_amount REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS refunds (
  refund_id TEXT PRIMARY KEY, order_id TEXT, amount REAL, reason TEXT,
  idempotency_key TEXT UNIQUE NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY, order_id TEXT, summary TEXT, reason TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY, order_id TEXT, amount REAL, reason TEXT, idempotency_key TEXT UNIQUE,
  status TEXT, decided_by TEXT, refund_id TEXT, created_at TEXT);
"""


class ToolError(Exception):
    """A problem the model should hear about and can fix (bad id, too large an amount...)."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OrderStore:
    """The fake backend. Infrastructure: given to you, not a part.

    OrderStore(":memory:") for tests; OrderStore("runs/store.db") to keep data between runs.
    """

    def __init__(self, path: str | Path = ":memory:", seed: str | Path | None = None):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        if seed and not self.db.execute("SELECT 1 FROM orders LIMIT 1").fetchone():
            self.seed(seed)

    def seed(self, path: str | Path) -> None:
        orders = json.loads(Path(path).read_text(encoding="utf-8"))
        with self.db:
            for o in orders:
                self.db.execute(
                    "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (o["order_id"], o["customer_name"], o["email"], o["phone"], o["card_last4"],
                     json.dumps(o["items"]), o["total"], o["status"], o["placed_at"], o["carrier"],
                     o["tracking"], o["eta"], o["delivered_at"], o["refunded_amount"]))

    def order(self, order_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        return d

    def rows(self, table: str) -> list[dict]:
        assert table in ("orders", "refunds", "tickets", "approvals")
        return [dict(r) for r in self.db.execute(f"SELECT * FROM {table} ORDER BY rowid")]

    def next_id(self, table: str, prefix: str) -> str:
        n = self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return f"{prefix}-{n + 1:04d}"


# ---------------------------------------------------------------- the tools

def lookup_order(store: OrderStore, order_id: str) -> dict:
    """Return the order as a dict. ToolError if the id is malformed or unknown.

    Normalize first (strip, upper case). Malformed: say what an order number looks like
    ("NW-1234"). Unknown: "No order NW-...", plus what the customer can do about it.
    """
    order_id = str(order_id).strip().upper()
    if not ORDER_ID_RE.match(order_id):
        raise ToolError(f"'{order_id}' is not an order number. Order numbers look like NW-1234.")
    order = store.order(order_id)
    if order is None:
        raise ToolError(f"No order {order_id}. Ask the customer to check the number on their confirmation email.")
    return order


def check_refundable(store: OrderStore, order_id: str, amount: float) -> tuple[dict, float, float]:
    """(order, amount rounded to cents, amount left to refund), or ToolError saying what is wrong.

    Errors, in this order: amount <= 0 ("more than $0"); status not in REFUNDABLE_STATUSES
    (say the status; for "processing" add that it "can be cancelled instead"); amount more
    than total - refunded_amount ("more than the $X.XX left to refund").
    """
    order = lookup_order(store, order_id)
    amount = round(float(amount), 2)
    refundable = round(order["total"] - order["refunded_amount"], 2)
    if amount <= 0:
        raise ToolError("Refund amount must be more than $0.")
    if order["status"] not in REFUNDABLE_STATUSES:
        hint = " It is still processing, so it can be cancelled instead." if order["status"] == "processing" else ""
        raise ToolError(f"Order {order['order_id']} is {order['status']}, so it cannot be refunded.{hint}")
    if amount > refundable:
        raise ToolError(f"Refund of ${amount:.2f} is more than the ${refundable:.2f} left to refund "
                        f"on {order['order_id']}.")
    return order, amount, refundable


def issue_refund(store: OrderStore, order_id: str, amount: float, reason: str, idempotency_key: str) -> dict:
    """Refund part or all of an order, exactly once per idempotency key.

    Same key again: return the first refund with "duplicate": True and change nothing.
    Same key with a different order or amount: ToolError (that is a bug, not a retry).
    """
    if not idempotency_key:
        raise ToolError("issue_refund needs an idempotency key")
    prior = store.db.execute("SELECT * FROM refunds WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    if prior is not None:
        if prior["order_id"] != str(order_id).upper() or abs(prior["amount"] - float(amount)) > 0.005:
            raise ToolError("This idempotency key was already used for a different refund.")
        return {**dict(prior), "status": "refunded", "duplicate": True}

    order, amount, refundable = check_refundable(store, order_id, amount)
    with store.db:   # one transaction: both writes happen, or neither does
        refund_id = store.next_id("refunds", "RF")
        store.db.execute("INSERT INTO refunds VALUES (?,?,?,?,?,?)",
                         (refund_id, order["order_id"], amount, reason, idempotency_key, now()))
        store.db.execute("UPDATE orders SET refunded_amount = refunded_amount + ?, status = 'refunded' "
                         "WHERE order_id = ?", (amount, order["order_id"]))
    return {"refund_id": refund_id, "order_id": order["order_id"], "amount": amount, "status": "refunded",
            "remaining": round(refundable - amount, 2), "duplicate": False}


def escalate_to_human(store: OrderStore, summary: str, reason: str, order_id: str | None = None) -> dict:
    """Open a ticket for a person to pick up."""
    if not summary or not summary.strip():
        raise ToolError("escalate_to_human needs a summary of the problem for the human agent.")
    with store.db:
        ticket_id = store.next_id("tickets", "ESC")
        store.db.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?)",
                         (ticket_id, order_id, summary.strip(), reason, "open", now()))
    return {"ticket_id": ticket_id, "status": "open", "eta": "1 business day"}


# ---------------------------------------------------------------- schemas and dispatch

TOOL_SCHEMAS = [
    {"name": "lookup_order",
     "description": "Look up one order by its number (like NW-1234). Returns items, total, status, carrier, "
                    "tracking number, delivery dates and how much has been refunded.",
     "input_schema": {"type": "object", "properties": {
         "order_id": {"type": "string", "description": "Order number, like NW-1234"}}, "required": ["order_id"]}},
    {"name": "issue_refund",
     "description": "Refund a delivered order to the original payment method. Only use when the customer asked "
                    "for a refund on their own order. Look the order up first. Refunds over $100 go to a human "
                    "for approval.",
     "input_schema": {"type": "object", "properties": {
         "order_id": {"type": "string"},
         "amount": {"type": "number", "description": "Dollars to refund, at most what is left on the order"},
         "reason": {"type": "string", "description": "One line, in the customer's words"}},
         "required": ["order_id", "amount", "reason"]}},
    {"name": "escalate_to_human",
     "description": "Hand the conversation to a human agent. Use when the customer asks for a person, is upset, "
                    "or the request is outside what you can do.",
     "input_schema": {"type": "object", "properties": {
         "summary": {"type": "string", "description": "What the customer needs, for the human agent"},
         "reason": {"type": "string", "enum": ["customer_request", "complaint", "out_of_scope", "tool_failure"]},
         "order_id": {"type": "string"}}, "required": ["summary", "reason"]}},
]
SCHEMAS_BY_NAME = {t["name"]: t for t in TOOL_SCHEMAS}


@dataclass
class ToolResult:
    name: str
    input: dict
    content: str          # what the model sees (JSON or an error sentence)
    is_error: bool = False
    data: dict | None = None


def make_idempotency_key(conversation_id: str, name: str, args: dict) -> str:
    """Same conversation + same tool + same arguments -> same key. A retry cannot double-refund."""
    canonical = json.dumps({"c": conversation_id, "t": name, "a": args}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def validate_args(name: str, args: dict) -> None:
    """Check required fields and basic types against the schema. ToolError on the first problem."""
    schema = SCHEMAS_BY_NAME[name]["input_schema"]
    for field in schema.get("required", []):
        if field not in args or args[field] in (None, ""):
            raise ToolError(f"{name} is missing required argument '{field}'.")
    for field, value in args.items():
        spec = schema["properties"].get(field)
        if spec is None:
            raise ToolError(f"{name} has no argument '{field}'. Arguments: {', '.join(schema['properties'])}.")
        if spec["type"] == "number" and not isinstance(value, (int, float)):
            try:
                float(value)
            except (TypeError, ValueError):
                raise ToolError(f"'{field}' must be a number, got {value!r}.") from None
        if "enum" in spec and value not in spec["enum"]:
            raise ToolError(f"'{field}' must be one of {spec['enum']}, got {value!r}.")


RefundGate = Callable[[OrderStore, dict, str], "dict | None"]


def run_tool(store: OrderStore, name: str, args: dict, conversation_id: str = "default",
             refund_gate: RefundGate | None = None) -> ToolResult:
    """Validate, run, and wrap one tool call. Never raises for a bad call: returns is_error instead.

    Unknown tool or validate_args failure -> ToolError. For issue_refund: upper-case the
    order_id, round the amount, and key = make_idempotency_key(conversation_id, name,
    {"order_id", "amount"}). Success: ToolResult(name, args, json.dumps(data), False, data).
    ToolError e: ToolResult(name, args, f"Error: {e}", True).

    refund_gate(store, args, key) runs before issue_refund. If it returns a dict, that dict is
    the result and no refund happens (part 5 uses this for human approval).
    """
    args = dict(args or {})
    try:
        if name not in SCHEMAS_BY_NAME:
            raise ToolError(f"Unknown tool '{name}'. Tools: {', '.join(SCHEMAS_BY_NAME)}.")
        validate_args(name, args)
        if name == "lookup_order":
            data = lookup_order(store, args["order_id"])
        elif name == "issue_refund":
            args["order_id"] = str(args["order_id"]).upper()
            args["amount"] = round(float(args["amount"]), 2)
            key = make_idempotency_key(conversation_id, name, {"order_id": args["order_id"], "amount": args["amount"]})
            gated = refund_gate(store, args, key) if refund_gate else None
            data = gated if gated is not None else issue_refund(store, args["order_id"], args["amount"],
                                                                args["reason"], key)
        else:
            data = escalate_to_human(store, args["summary"], args["reason"], args.get("order_id"))
        return ToolResult(name, args, json.dumps(data), False, data)
    except ToolError as e:
        return ToolResult(name, args, f"Error: {e}", True)
