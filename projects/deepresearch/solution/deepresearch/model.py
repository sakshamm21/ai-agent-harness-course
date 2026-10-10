"""Model interface: a rule-based offline mock for every agent role, and a real Anthropic model.

Messages use the Anthropic Messages API shape:
    {"role": "user" | "assistant", "content": str | list[block]}
Blocks: {"type": "text"}, {"type": "tool_use", "id", "name", "input"},
        {"type": "tool_result", "tool_use_id", "content", "is_error"?}
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from .textutil import extract_json, keywords, sentences, supports, tokenize
from .tokens import count_message_tokens, count_tokens


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
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)

    def to_message(self) -> dict:
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        return {"role": "assistant", "content": blocks}


class Model:
    """Anything with complete(). `tier` picks the sim price (small | medium | large)."""

    name = "model"
    tier = "medium"

    def complete(self, messages: list[dict], tools: list[dict] | None = None, system: str | None = None,
                 temperature: float = 0.0, max_tokens: int = 1500) -> Response:
        raise NotImplementedError


def _estimate_usage(messages, tools, system, resp: Response) -> Usage:
    inp = count_tokens(system or "") + sum(count_message_tokens(m) for m in messages)
    inp += sum(count_tokens(json.dumps(t)) for t in (tools or []))
    out = count_tokens(resp.text) + sum(count_tokens(json.dumps(c.input)) + 10 for c in resp.tool_calls)
    return Usage(inp, out)


class MockModel(Model):
    """A scripted model for tests: a list of Responses (last repeats) or a function (messages, tools, system) -> Response."""

    name = "mock-scripted"

    def __init__(self, script: list[Response] | Callable[..., Response], tier: str = "small"):
        self.script = script
        self.tier = tier
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1500):
        with self._lock:
            self.calls += 1
            n = self.calls
        if isinstance(self.script, list):
            r = self.script[min(n - 1, len(self.script) - 1)]
        else:
            r = self.script(messages, tools, system)
        resp = Response(r.text, list(r.tool_calls), "tool_use" if r.tool_calls else "end_turn")
        resp.usage = _estimate_usage(messages, tools, system, resp)
        return resp


class ResearchMock(Model):
    """A deterministic, rule-based stand-in for every agent in deepresearch.

    It reads the "Role: <name>." line of the system prompt and plays that role with
    simple text rules. It is not smart, and it makes one mistake on purpose: a worker
    cites the first page it read for every claim, the way a hurried model anchors on its
    first source. The citation verifier (part 4) exists to catch exactly that.
    """

    name = "mock"

    def __init__(self, tier: str = "medium"):
        self.tier = tier
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1500):
        with self._lock:
            self.calls += 1
        m = re.search(r"Role:\s*(\w+)", system or "")
        role = m.group(1).lower() if m else "chat"
        handler = getattr(self, "_" + role, None)
        resp = handler(messages) if handler else Response(text="I can only play deepresearch roles.")
        if resp.tool_calls:
            resp.stop_reason = "tool_use"
        resp.usage = _estimate_usage(messages, tools, system, resp)
        return resp

    # --- planner ---------------------------------------------------------------
    def _planner(self, messages) -> Response:
        text = _first_user_text(messages)
        q = _field(text, "Question")
        n = int((re.search(r"at most (\d+)", text) or [0, 4])[1])
        return Response(text=json.dumps(_split_question(q)[:n]))

    def _replanner(self, messages) -> Response:
        text = _first_user_text(messages)
        failed = re.findall(r"^- (.+)$", text.split("Failed:", 1)[1], re.M) if "Failed:" in text else []
        out = []
        for f in failed:
            k = keywords(f)
            out.append(k if k != f.lower() else k + " overview")
        return Response(text=json.dumps(out))

    # --- worker ----------------------------------------------------------------
    def _worker(self, messages) -> Response:
        subq = _field(_first_user_text(messages), "Sub-question")
        results = _tool_results(messages)  # [(name, input, content, is_error)]
        searches = [r for r in results if r[0] == "search"]
        fetches = [r for r in results if r[0] == "fetch_page" and not r[3]]
        if not searches:
            return Response(tool_calls=[ToolCall("call_s1", "search", {"query": keywords(subq)})])
        if not fetches and not any(r[0] == "fetch_page" for r in results):
            hits = _loads(searches[-1][2]) if not searches[-1][3] else None
            if not hits:
                return Response(text=json.dumps({"claims": []}))
            ids = [h["id"] for h in hits[:2]]
            return Response(tool_calls=[ToolCall(f"call_f{i}", "fetch_page", {"doc_id": d}) for i, d in enumerate(ids, 1)])
        pages = [p for p in (_loads(r[2]) for r in fetches) if isinstance(p, dict) and p.get("text")]
        if not pages:
            return Response(text=json.dumps({"claims": []}))
        q = set(tokenize(subq))
        claims = []
        anchor = pages[0]["id"]  # the deliberate mistake: every claim cites the first page read
        for p in pages:
            scored = sorted(((len(q & set(tokenize(s))), i, s) for i, s in enumerate(sentences(p["text"]))),
                            key=lambda x: (-x[0], x[1]))
            for score, _, s in scored[:2]:
                if score >= 2:
                    claims.append({"text": s, "sources": [anchor]})
        return Response(text=json.dumps({"claims": claims}))

    # --- verifier and reviser --------------------------------------------------
    def _verifier(self, messages) -> Response:
        text = _first_user_text(messages)
        claim = _field(text, "Claim")
        m = re.search(r"\nSource [^\n]*:\n(.*?)\n\nReply with JSON", text, re.S)
        source = m.group(1) if m else ""
        ok = supports(claim, source)
        reason = "The source states this." if ok else "The source does not state this claim."
        return Response(text=json.dumps({"supported": ok, "reason": reason}))

    def _reviser(self, messages) -> Response:
        text = _first_user_text(messages)
        drafts = (extract_json(_between(text, "Draft claims (JSON):", "Verifier feedback")) or {}).get("claims", [])
        feedback = extract_json(_between(text, "Verifier feedback (JSON):", "Pages you read:")) or []
        pages = dict(re.findall(r"^=== (\S+)\n(.*?)(?=^=== )", text, re.S | re.M))
        rejected = {f.get("claim") for f in feedback}
        out = []
        for c in drafts:
            if c["text"] not in rejected:
                out.append(c)
                continue
            good = [pid for pid, body in pages.items() if pid != "end" and supports(c["text"], body)]
            if good:
                out.append({"text": c["text"], "sources": good[:1]})
        return Response(text=json.dumps({"claims": out}))

    # --- writer ----------------------------------------------------------------
    def _writer(self, messages) -> Response:
        text = _first_user_text(messages)
        h = extract_json(text.split("Findings (JSON):", 1)[-1]) or {}
        sections = [s for s in h.get("sections", []) if s.get("claims")]
        n_src = len({d for s in sections for c in s["claims"] for d in c["sources"]})
        lines = [f"# {h.get('question', 'Research report')}", "",
                 f"This report answers {len(sections)} sub-questions from {n_src} sources.", ""]
        for s in sections:
            lines += [f"## {s['sub_question']}", ""]
            for c in s["claims"]:
                lines.append(f"- {c['text'].rstrip('.')} [{', '.join(c['sources'])}].")
            lines.append("")
        if h.get("gaps"):
            lines += ["## Gaps", ""] + [f"- Not answered: {g}" for g in h["gaps"]] + [""]
        return Response(text="\n".join(lines).rstrip() + "\n")


# --- helpers for the mock ---------------------------------------------------------

_SPLIT = re.compile(r",\s*and\s+|;\s*|\?\s+|\s+and\s+(?=(?:what|when|where|who|whom|why|how|which|is|are|was|were|did|does|do)\b)", re.I)
_WH = {"what", "when", "where", "who", "why", "how", "which", "is", "are", "was", "were", "did", "does", "do"}


def _split_question(q: str) -> list[str]:
    q = q.strip()
    clauses = [c.strip(" ?.,") for c in _SPLIT.split(q) if c and len(c.split()) >= 3]
    if not clauses:
        return [q]
    first = clauses[0]
    names = [w.strip(",?") for w in first.split()[1:] if w[:1].isupper() and w.lower() not in _WH]
    subject = " ".join(names)
    out = []
    for c in clauses:
        has_name = any(w[:1].isupper() for w in c.split()[1:])
        c = c[0].upper() + c[1:]
        out.append(f"{c} ({subject})?" if subject and not has_name else c + "?")
    return list(dict.fromkeys(out))


def _first_user_text(messages) -> str:
    for m in messages:
        if m["role"] == "user":
            c = m["content"]
            return c if isinstance(c, str) else " ".join(b.get("text", "") for b in c if b.get("type") == "text")
    return ""


def _field(text: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else text.strip()


def _between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[-1].split(end, 1)[0]


def _loads(s):
    try:
        return json.loads(s)
    except (TypeError, json.JSONDecodeError):
        return None


def _tool_results(messages) -> list[tuple]:
    uses = {}
    out = []
    for m in messages:
        if not isinstance(m["content"], list):
            continue
        for b in m["content"]:
            if b.get("type") == "tool_use":
                uses[b["id"]] = (b["name"], b["input"])
            elif b.get("type") == "tool_result":
                name, inp = uses.get(b["tool_use_id"], ("?", {}))
                out.append((name, inp, b.get("content"), bool(b.get("is_error"))))
    return out


# --- the real model ------------------------------------------------------------------

class AnthropicModel(Model):
    """Calls the Anthropic Messages API with urllib (stdlib only)."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5-5"):
        self.api_key = api_key
        self.model = model
        self.name = model
        self.tier = tier_for(model)

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1500):
        import urllib.error
        import urllib.request
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "messages": messages,
                                "temperature": temperature}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(self.URL, json.dumps(body).encode(), {
            "x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            data = json.loads(e.read() or b'{"error": {"message": "HTTP error"}}')
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        calls = [ToolCall(b["id"], b["name"], b["input"]) for b in data["content"] if b["type"] == "tool_use"]
        u = data.get("usage", {})
        return Response(text, calls, data.get("stop_reason", "end_turn"),
                        Usage(u.get("input_tokens", 0), u.get("output_tokens", 0)))


# Which model plays which role with a real API key. Override with DEEPRESEARCH_<ROLE>_MODEL.
MODEL_DEFAULTS = {
    "planner": "claude-sonnet-5-5",
    "writer": "claude-sonnet-5-5",
    "worker": "claude-haiku-5-5",
    "verifier": "claude-haiku-5-5",
    "reviser": "claude-haiku-5-5",
}


def tier_for(model_name: str) -> str:
    n = model_name.lower()
    return "small" if "haiku" in n else "large" if "opus" in n else "medium"


def use_mock() -> bool:
    return os.environ.get("DEEPRESEARCH_MOCK") == "1" or not os.environ.get("ANTHROPIC_API_KEY")


def get_models(mock: bool | None = None) -> dict[str, Model]:
    """One model per role. Mock unless ANTHROPIC_API_KEY is set (and DEEPRESEARCH_MOCK is not 1)."""
    if mock is None:
        mock = use_mock()
    models: dict[str, Model] = {}
    for role, default in MODEL_DEFAULTS.items():
        name = os.environ.get(f"DEEPRESEARCH_{role.upper()}_MODEL", default)
        models[role] = ResearchMock(tier_for(name)) if mock else AnthropicModel(os.environ["ANTHROPIC_API_KEY"], name)
    return models
