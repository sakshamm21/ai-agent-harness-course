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
        conv = conversation_id or uuid.uuid4().hex[:12]
        history = history or []
        events: list[dict] = []
        usage = Usage()
        previous = [m["content"] for m in history if m["role"] == "user" and isinstance(m["content"], str)]
        self._emit(events, conv, "user_message", text=message)

        # 1. route (small model), 2. retrieve
        t0 = time.time()
        r = route(routing_text(message, previous), self.router_model)
        self._emit(events, conv, "route", label=r.label, source=r.source, duration_ms=_ms(t0))
        t0 = time.time()
        hits = retrieve(self.index, message, k=3)
        self._emit(events, conv, "retrieve", query=message, duration_ms=_ms(t0),
                   hits=[{"article_id": h["article_id"], "score": h["score"]} for h in hits])
        if self.trust_boundary:
            for h in hits:
                signals = security.injection_signals(h["text"])
                if signals:
                    self._emit(events, conv, "suspicious_document", article_id=h["article_id"], signals=signals)

        # 3. the loop, with only this route's tools
        allowed = TOOLS_BY_ROUTE[r.label]
        tools = [SCHEMAS_BY_NAME[n] for n in allowed]
        ctx = security.ToolContext.build(r.label, allowed, previous + [message])
        gate = guardrails.refund_gate if self.guardrails else None
        system, messages = self.build_context(r.label, message, history, hits)
        calls: list[dict] = []
        final = None
        for turn in range(1, self.max_turns + 1):
            t0 = time.time()
            resp = self.model.complete(messages, tools=tools, system=system, temperature=0.0)
            usage = usage + resp.usage
            self._emit(events, conv, "model_call", turn=turn, model=getattr(self.model, "name", "model"),
                       duration_ms=_ms(t0), text=resp.text, tool_calls=[c.name for c in resp.tool_calls],
                       input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
            messages.append(resp.to_message())
            if not resp.tool_calls:
                final = resp.text
                break
            results = []
            for call in resp.tool_calls:
                t0 = time.time()
                ok, why = security.authorize_tool_call(call.name, call.input, ctx) if self.trust_boundary \
                    else (call.name in allowed, "ok" if call.name in allowed else "tool not offered")
                if not ok:
                    content, is_error = f"Blocked: {why}. Do not retry this call.", True
                    self._emit(events, conv, "blocked", name=call.name, input=call.input, reason=why)
                    calls.append({"name": call.name, "input": call.input, "is_error": True,
                                  "content": content, "blocked": True})
                else:
                    res = run_tool(self.store, call.name, call.input, conv, refund_gate=gate)
                    content, is_error = res.content, res.is_error
                    self._emit(events, conv, "tool_call", name=call.name, input=res.input, output=_short(content),
                               is_error=is_error, duration_ms=_ms(t0))
                    calls.append({"name": call.name, "input": res.input, "is_error": is_error,
                                  "content": content, "blocked": False})
                block = {"type": "tool_result", "tool_use_id": call.id, "content": content}
                if is_error:
                    block["is_error"] = True
                results.append(block)
            messages.append({"role": "user", "content": results})

        if final is None:
            final = FALLBACK
            self._emit(events, conv, "max_turns", turns=self.max_turns)

        # 4. check citations, then guard the output
        text, cited, invalid = check_citations(final.strip(), hits)
        if invalid:
            self._emit(events, conv, "invalid_citations", ids=invalid)
        if self.guardrails:
            text, redacted = guardrails.redact_pii(text)
            if redacted:
                self._emit(events, conv, "redacted", counts=redacted)
        self._emit(events, conv, "final", text=text, route=r.label, citations=cited,
                   input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        return Reply(text, r.label, conv, cited, calls, events, usage)


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
