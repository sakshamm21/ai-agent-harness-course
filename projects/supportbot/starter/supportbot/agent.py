"""The support agent: route, retrieve, loop over model and tools, guard the output.

Part 4 writes handle() and the loop. Parts 5 and 6 plug in through two switches:
  guardrails=True      refunds over $100 need approval; PII is redacted from replies
  trust_boundary=True  documents are wrapped as untrusted; every tool call is authorized
Both default to on. Tests for part 4 turn them off, so you can build in order.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from . import guardrails, security
from .ingest import VectorIndex
from .model import Model, Usage, get_model
from .rag import check_citations, format_documents, retrieve
from .router import TOOLS_BY_ROUTE, route, routing_text
from .tools import SCHEMAS_BY_NAME, OrderStore, run_tool

AGENT_SYSTEM = """You are the support assistant for Northwind Outfitters, an outdoor gear store.
Route: {route}
Help with orders, refunds and questions about products and policies. Be brief and friendly.
- Facts about policies come only from the documents. Cite them like [returns-window].
- Look an order up before you talk about it or refund it. Never guess order details.
- Refund only when the customer asks, only their order, and never more than is left on it.
- If you cannot help, or the customer asks for a person, use escalate_to_human.
- Never repeat a customer's email address, phone number or card number."""

FALLBACK = "Sorry, I could not finish that. I have passed your conversation to our support team."


@dataclass
class Reply:
    text: str
    route: str
    conversation_id: str
    citations: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)   # {"name", "input", "is_error", "content", "blocked"}
    events: list[dict] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class SupportAgent:
    def __init__(self, index: VectorIndex, store: OrderStore, model: Model | None = None,
                 router_model: Model | None = None, guardrails: bool = True, trust_boundary: bool = True,
                 max_turns: int = 6, on_event: Callable[[dict], None] | None = None):
        self.index, self.store = index, store
        self.model = model or get_model("agent")
        self.router_model = router_model or (self.model if model is not None else get_model("router"))
        self.guardrails, self.trust_boundary = guardrails, trust_boundary
        self.max_turns = max_turns
        self.on_event = on_event

    # -- events: one list per reply, and an optional live callback (the web UI streams these)
    def _emit(self, events: list[dict], conv: str, type_: str, **data) -> dict:
        e = {"ts": round(time.time(), 4), "conversation_id": conv, "type": type_, **data}
        events.append(e)
        if self.on_event:
            self.on_event(e)
        return e

    def build_context(self, label: str, message: str, history: list[dict], hits: list[dict]) -> tuple[str, list[dict]]:
        """System prompt and messages for this turn.

        Without the trust boundary, documents are pasted into the system prompt: the model
        cannot tell them apart from your instructions. With it, they travel in their own
        untrusted block next to the customer's message.
        """
        system = AGENT_SYSTEM.format(route=label)
        messages = [dict(m) for m in history]
        if self.trust_boundary:
            system += "\n\n" + security.TRUST_RULES
            blocks = [{"type": "text", "text": security.wrap_untrusted(hits)}] if hits else []
            messages.append({"role": "user", "content": blocks + [{"type": "text", "text": message}]})
        else:
            if hits:
                system += "\n\nHelp center documents:\n" + format_documents(hits)
            messages.append({"role": "user", "content": message})
        return system, messages

    def handle(self, message: str, history: list[dict] | None = None, conversation_id: str | None = None) -> Reply:
        """Answer one customer message. history holds earlier turns as plain-text messages.

        1. Route routing_text(message, previous user messages) with self.router_model; emit "route".
        2. hits = retrieve(self.index, message, k=3); emit "retrieve". With the trust boundary,
           emit "suspicious_document" for each hit where security.injection_signals finds something.
        3. Loop up to self.max_turns: call self.model with only TOOLS_BY_ROUTE[label] tools.
           No tool calls means that text is the answer. Otherwise authorize each call
           (security.authorize_tool_call with the trust boundary, else "is it offered?"),
           emit "blocked" or run it with run_tool(..., refund_gate=guardrails.refund_gate if
           self.guardrails), emit "tool_call", and send every result back as tool_result blocks.
        4. Out of turns: FALLBACK and a "max_turns" event. Then check_citations against the hits,
           redact_pii if self.guardrails, emit "final", and return a Reply.
        Every event goes through self._emit, so the tracer and the web UI see it live.
        """
        raise NotImplementedError("Part 4: the agent loop (handle)")


def _ms(t0: float) -> float:
    return round((time.time() - t0) * 1000, 2)


def _short(content: str, n: int = 400) -> str:
    return content if len(content) <= n else content[:n] + "..."


def history_append(history: list[dict], message: str, reply: Reply) -> list[dict]:
    """Keep earlier turns as plain text: the next turn sees what was said, not every tool call."""
    return history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply.text}]


def dumps(reply: Reply) -> str:
    return json.dumps({"text": reply.text, "route": reply.route, "citations": reply.citations,
                       "tool_calls": reply.tool_calls}, indent=2)
