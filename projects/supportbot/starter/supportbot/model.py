"""Models: a deterministic MockModel that runs offline, and AnthropicModel for real calls.

This file is infrastructure, not a part. You do not need to edit it.

Messages use the Anthropic Messages API shape:
    {"role": "user" | "assistant", "content": str | list[block]}
Blocks: {"type": "text", "text"}, {"type": "tool_use", "id", "name", "input"},
        {"type": "tool_result", "tool_use_id", "content", "is_error"?}

The MockModel reads the same prompts a real model would, and plays three roles:
  - router  (system prompt contains ROUTER_MARK): replies with one route label
  - judge   (system prompt contains JUDGE_MARK): replies with a JSON verdict
  - support (everything else): answers from <document> blocks with [article-id]
    citations, and calls tools when the conversation needs them.
It is deliberately gullible: if any text in its context says "call <tool> with
order_id X and amount N", it tries to do exactly that. Part 6 is about making
sure that cannot hurt you.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MODEL = "claude-sonnet-5-5"   # answers, tool use, judging
ROUTER_MODEL = "claude-haiku-5-5"     # cheap and fast: routing only

ROUTER_MARK = "You route customer support messages"
JUDGE_MARK = "You grade customer support answers"
ROUTES = ("refund", "order_status", "product_question", "other")

# $ per million tokens (input, output). Illustrative; check the pricing page.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "mock": (0.0, 0.0)}


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens)


@dataclass
class Response:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens"
    usage: Usage = field(default_factory=Usage)

    def to_message(self) -> dict:
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        return {"role": "assistant", "content": blocks}


class Model:
    name = "model"

    def complete(self, messages: list[dict], tools: list[dict] | None = None, system: str | None = None,
                 temperature: float = 0.0, max_tokens: int = 1024) -> Response:
        raise NotImplementedError


def _tokens(text: str) -> int:
    return max(1, round(len(text) / 4)) if text else 0


# --------------------------------------------------------------------------- mock

class MockModel(Model):
    """Offline, deterministic stand-in for Claude. Same input, same output, every time."""

    name = "mock"

    def __init__(self):
        self.calls = 0
        self.log: list[dict] = []

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
        self.calls += 1
        system = system or ""
        if ROUTER_MARK in system:
            users = _user_texts(messages)
            resp = Response(text=_mock_route(users[-1] if users else ""))
        elif JUDGE_MARK in system:
            resp = Response(text=_mock_judge(_all_text(messages)))
        else:
            resp = _support_policy(system, messages, tools or [], self.calls)
        if resp.tool_calls:
            resp.stop_reason = "tool_use"
        context = system + json.dumps(messages) + json.dumps(tools or [])
        resp.usage = Usage(_tokens(context), _tokens(resp.text) + 20 * len(resp.tool_calls))
        self.log.append({"system": system[:60], "tools": [t["name"] for t in tools or []],
                         "text": resp.text, "tool_calls": [(c.name, c.input) for c in resp.tool_calls]})
        return resp


# -- reading the context ----------------------------------------------------

DOC_RE = re.compile(r'<document id="([^"]+)"[^>]*>(.*?)</document>', re.S)
ORDER_RE = re.compile(r"\bNW-\d{4}\b", re.I)
INJECT_RE = re.compile(r"call (\w+) with order_id (NW-\d{4}) and amount (\d+(?:\.\d+)?)", re.I)
MONEY_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")


def _blocks(m: dict) -> list[dict]:
    c = m.get("content", "")
    return [{"type": "text", "text": c}] if isinstance(c, str) else c


def _user_texts(messages: list[dict]) -> list[str]:
    """Text the customer typed. Document blocks and tool results are not customer text."""
    out = []
    for m in messages:
        if m["role"] != "user":
            continue
        texts = [re.sub(r"<documents.*?</documents>", "", b["text"], flags=re.S).strip()
                 for b in _blocks(m) if b.get("type") == "text"]
        texts = [t for t in texts if t]
        if texts:
            out.append(" ".join(texts))
    return out


def _all_text(messages: list[dict], system: str = "") -> str:
    parts = [system]
    for m in messages:
        for b in _blocks(m):
            if b.get("type") == "text":
                parts.append(b["text"])
            elif b.get("type") == "tool_result":
                parts.append(str(b.get("content", "")))
    return "\n".join(parts)


def _tool_history(messages: list[dict]) -> list[dict]:
    """Every tool call so far with its result: [{"name", "input", "result", "is_error"}]."""
    calls: dict[str, dict] = {}
    order: list[str] = []
    for m in messages:
        for b in _blocks(m):
            if b.get("type") == "tool_use":
                calls[b["id"]] = {"name": b["name"], "input": b["input"], "result": None, "is_error": False}
                order.append(b["id"])
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                c = calls[b["tool_use_id"]]
                c["result"], c["is_error"] = b.get("content"), bool(b.get("is_error"))
    return [calls[i] for i in order]


def _json(s: Any) -> dict:
    try:
        v = json.loads(s) if isinstance(s, str) else s
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


# -- words ------------------------------------------------------------------

_STOP = set("""a an the is are was were be been am i me my mine you your yours we our us it its this that these
those to of and or in on at for with from by as do does did can could would should will shall may might
how what when where which who whom why there here have has had not no yes so if then than too very just
about into out up down over any some all get got please hi hello thanks thank want need like know tell
im ive dont cant does s t""".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


# A real model knows these mean the same thing; the mock needs a hint.
_SAME = {"money": "refund", "reimburse": "refund", "soon": "day", "when": "day", "time": "day",
         "installment": "instalment", "installments": "instalment", "broken": "damag", "damaged": "damag",
         "damage": "damag", "wash": "clean", "washing": "clean", "canada": "countri", "abroad": "countri",
         "international": "countri", "overseas": "countri", "cost": "price", "costs": "price", "fee": "price"}


def _content_words(text: str) -> set[str]:
    out = set()
    text = re.sub(r"\bhow long\b", "when", text.lower())
    for w in re.findall(r"[a-z0-9]+", text):
        if w in _SAME:
            out.add(_SAME[w])
        elif w not in _STOP and len(w) > 1:
            out.add(_stem(w))
    return out


def _sentences(text: str) -> list[str]:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    flat = " ".join(lines)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if len(s.strip()) > 3]


def _best_sentences(question: str, docs: list[tuple[str, str]], n: int = 2) -> list[tuple[str, str, int]]:
    """Pick the n sentences that share the most words with the question, as (sentence, doc_id, score)."""
    q = _content_words(question)
    scored = []
    for rank, (doc_id, text) in enumerate(docs):
        title, _, body = text.partition("\n")
        title_bonus = len(q & _content_words(title))
        for i, s in enumerate(_sentences(body if body else text)):
            overlap = len(q & _content_words(s))
            if overlap:
                # prefer early sentences, the article whose title matches, and higher-ranked documents
                scored.append((overlap + 0.5 * title_bonus - 0.3 * rank - 0.05 * i, s, doc_id, overlap))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, s, doc_id, overlap in scored:
        if s not in seen:
            seen.add(s)
            out.append((s, doc_id, overlap))
        if len(out) == n:
            break
    return out


def _extractive_answer(question: str, docs: list[tuple[str, str]]) -> str | None:
    best = _best_sentences(question, docs, n=2)
    if not best:
        return None
    return " ".join(f"{s} [{d}]" for s, d, _ in best)


# -- roles ------------------------------------------------------------------

def _mock_route(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(human|person|real agent|manager|supervisor|complain|complaint|lawyer|speak to|talk to)\b", t):
        return "other"
    if re.search(r"\b(refunds?|money back|reimburse|charge ?back)\b", t):
        # "how long do refunds take?" is a policy question; "refund my order" is a request
        if not ORDER_RE.search(t) and re.match(r"\s*(how|why|what|when|which|do|does|are|is)\b", t):
            return "product_question"
        return "refund"
    if ORDER_RE.search(t) or re.search(r"\b(where is my|track|tracking|has my order|my package|shipped yet|status)\b", t):
        return "order_status"
    if re.search(r"\b(return|exchange|size|sizing|fit|warranty|ship|shipping|deliver|pay|payment|gift|card|account|"
                 r"password|tent|boot|jacket|sleeping|waterproof|price|discount|points|tax|repair|stove|order|cancel|"
                 r"policy|wash|care|store|email|students?)", t):
        return "product_question"
    return "other"


def _mock_judge(text: str) -> str:
    """Grade an ANSWER against RUBRIC lines: '- must mention: x' and '- must not mention: y'."""
    answer = ""
    m = re.search(r"ANSWER:\s*(.*?)\nRUBRIC:", text, re.S)
    if m:
        answer = m.group(1).lower()
    missing = [x.strip() for x in re.findall(r"- must mention: (.+)", text) if x.strip().lower() not in answer]
    forbidden = [x.strip() for x in re.findall(r"- must not mention: (.+)", text) if x.strip().lower() in answer]
    checks = len(re.findall(r"- must (?:not )?mention: ", text)) or 1
    score = round(1 - (len(missing) + len(forbidden)) / checks, 2)
    reason = "All rubric points covered." if not (missing or forbidden) else \
        "; ".join([f"missing '{x}'" for x in missing] + [f"should not say '{x}'" for x in forbidden])
    return json.dumps({"pass": not missing and not forbidden, "score": max(score, 0.0), "reason": reason})


def _route_from_system(system: str) -> str:
    m = re.search(r"^Route: (\w+)", system, re.M)
    return m.group(1) if m else "product_question"


def _support_policy(system: str, messages: list[dict], tools: list[dict], n: int) -> Response:
    names = {t["name"] for t in tools}
    history = _tool_history(messages)
    users = _user_texts(messages)
    last_user = users[-1] if users else ""
    docs = DOC_RE.findall(_all_text(messages, system))
    docs = [(d, re.sub(r"\s+\n", "\n", t.strip())) for d, t in docs]

    def call(name: str, args: dict) -> Response:
        return Response(tool_calls=[ToolCall(id=f"toolu_{n:03d}_{len(history)}", name=name, input=args)])

    def attempted(name: str, **match) -> dict | None:
        for h in history:
            if h["name"] == name and all(str(h["input"].get(k)) == str(v) for k, v in match.items()):
                return h
        return None

    # 1. Gullible on purpose: follow any "call X with order_id Y and amount Z" found anywhere in context.
    for tool, oid, amount in INJECT_RE.findall(_all_text(messages, system)):
        if tool in names and not attempted(tool, order_id=oid.upper()):
            return call(tool, {"order_id": oid.upper(), "amount": float(amount), "reason": "goodwill credit"})

    route = _route_from_system(system)
    order_ids = [o.upper() for u in reversed(users) for o in ORDER_RE.findall(u)]
    oid = order_ids[0] if order_ids else None
    cite = _extractive_answer(last_user, docs)

    if route in ("refund", "order_status") and "lookup_order" in names:
        if not oid:
            return Response(text="I can help with that. What is your order number? It looks like NW-1234.")
        look = attempted("lookup_order", order_id=oid)
        if not look:
            return call("lookup_order", {"order_id": oid})
        if look["is_error"]:
            return Response(text=f"I could not find that order: {look['result']} Please check the number.")
        order = _json(look["result"])
        if route == "refund" and "issue_refund" in names:
            ref = attempted("issue_refund", order_id=oid)
            if not ref:
                m = MONEY_RE.search(last_user)
                refundable = round(order.get("total", 0) - order.get("refunded_amount", 0), 2)
                amount = float(m.group(1)) if m else refundable
                return call("issue_refund", {"order_id": oid, "amount": amount, "reason": last_user[:120]})
            return Response(text=_refund_text(oid, ref, order, docs))
        return Response(text=_status_text(order))

    if route == "other" and "escalate_to_human" in names:
        esc = attempted("escalate_to_human")
        if not esc and re.search(r"\b(human|person|agent|manager|supervisor|complain|complaint|speak|talk)\b", last_user.lower()):
            args = {"summary": last_user[:200], "reason": "customer_request"}
            if oid:
                args["order_id"] = oid
            return call("escalate_to_human", args)
        if esc:
            r = _json(esc["result"])
            return Response(text=f"I've passed this to our support team (ticket {r.get('ticket_id', '?')}). "
                                 f"A person will reply by email within {r.get('eta', '1 business day')}.")

    if cite and route != "other":      # "other" is small talk or off topic: do not force an article on it
        return Response(text=cite)
    return Response(text="I could not find that in our help center. I can help with orders, refunds and questions "
                         "about our products and policies, or pass you to a person.")


def _status_text(o: dict) -> str:
    items = ", ".join(i["name"] for i in o.get("items", []))
    s = o.get("status")
    head = f"Order {o.get('order_id')} ({items})"
    if s == "shipped":
        body = f"has shipped with {o.get('carrier')}, tracking number {o.get('tracking')}. Expected delivery: {o.get('eta')}."
    elif s == "delivered":
        body = f"was delivered on {o.get('delivered_at')}."
    elif s == "processing":
        body = "is processing. It usually leaves our warehouse within 1 business day."
    elif s == "cancelled":
        body = "was cancelled, and you were not charged."
    else:
        body = f"has status {s}. Refunded so far: ${o.get('refunded_amount', 0):.2f}."
    return f"{head} {body} We send updates to {o.get('email')}."


def _refund_text(oid: str, ref: dict, order: dict, docs: list[tuple[str, str]]) -> str:
    r = _json(ref["result"])
    if ref["is_error"]:
        return f"I could not refund order {oid}: {ref['result']}"
    if r.get("status") == "pending_approval":
        cite = " [refund-approval]" if any(d == "refund-approval" for d, _ in docs) else ""
        return (f"Refunds over $100 are reviewed by our team before they are issued{cite}. I've sent your "
                f"${r.get('amount', 0):.2f} refund for order {oid} for approval (request {r.get('approval_id')}). "
                "You will get an email when it is approved.")
    cite = " [refund-timing]" if any(d == "refund-timing" for d, _ in docs) else ""
    return (f"Done. I've refunded ${r.get('amount', 0):.2f} for order {oid} (refund {r.get('refund_id')}) to the card "
            f"ending in {order.get('card_last4')}. Your bank usually takes 5 to 10 business days to show it{cite}.")


# --------------------------------------------------------------------------- real model

class AnthropicModel(Model):
    """Calls the Anthropic Messages API with urllib. No SDK needed."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, retries: int = 2):
        self.api_key, self.model, self.retries = api_key, model, retries
        self.name = model

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
        # temperature is accepted for the shared interface but not sent: some current models
        # reject it, and the mock is where determinism comes from in this project.
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(self.URL, json.dumps(body).encode(), {
            "x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            method="POST")
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 529, 500) and attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Anthropic API error {e.code}: {e.read()[:300]!r}") from e
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        calls = [ToolCall(b["id"], b["name"], b["input"]) for b in data["content"] if b["type"] == "tool_use"]
        u = data.get("usage", {})
        return Response(text, calls, data.get("stop_reason", "end_turn"),
                        Usage(u.get("input_tokens", 0), u.get("output_tokens", 0)))


def get_model(role: str = "agent") -> Model:
    """MockModel unless ANTHROPIC_API_KEY is set. role "router" gets the small, fast model."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or os.environ.get("SUPPORTBOT_MOCK") == "1":
        return MockModel()
    if role == "router":
        return AnthropicModel(key, os.environ.get("SUPPORTBOT_ROUTER_MODEL", ROUTER_MODEL))
    return AnthropicModel(key, os.environ.get("SUPPORTBOT_MODEL", DEFAULT_MODEL))
