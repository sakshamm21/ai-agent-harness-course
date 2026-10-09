"""Model interface: a MockModel that runs offline and an AnthropicModel for real calls.

Messages use the Anthropic Messages API shape:
    {"role": "user" | "assistant", "content": str | list[block]}
Blocks: {"type": "text", "text": ...}, {"type": "tool_use", "id", "name", "input"},
        {"type": "tool_result", "tool_use_id", "content", "is_error"?}
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from .tokens import count_tokens, count_message_tokens


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
        """The assistant message to append to the transcript."""
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        return {"role": "assistant", "content": blocks}


class Model:
    """Anything with complete(). Subclass it to plug in any provider."""

    name = "model"

    def complete(self, messages: list[dict], tools: list[dict] | None = None, system: str | None = None,
                 temperature: float = 1.0, max_tokens: int = 1024) -> Response:
        raise NotImplementedError

    def stream(self, messages: list[dict], **kw) -> Iterator[dict]:
        """Yield {"type": "text_delta", "text"} events, then {"type": "done", "response"}."""
        resp = self.complete(messages, **kw)
        words = resp.text.split(" ")
        for i, w in enumerate(words):
            yield {"type": "text_delta", "text": w + (" " if i < len(words) - 1 else "")}
        for c in resp.tool_calls:
            yield {"type": "tool_use", "name": c.name, "input": c.input}
        yield {"type": "done", "response": resp}


Script = Callable[[list[dict], list[dict] | None], Response]


class MockModel(Model):
    """A scripted, offline model.

    Give it either:
      - a list of Responses (returned in order, the last one repeats), or
      - a function (messages, tools) -> Response, or
      - nothing, for a tiny rule-based default that calls a tool whose name
        appears in the last user message, then answers with the tool result.
    `temperature` adds seeded word-level variation to text answers, so lessons
    can show variance without a network.
    """

    name = "mock"

    def __init__(self, script: list[Response] | Script | None = None, seed: int = 0):
        self.script = script
        self.calls = 0
        self.rng = random.Random(seed)
        self.log: list[dict] = []

    def complete(self, messages, tools=None, system=None, temperature=1.0, max_tokens=1024):
        self.calls += 1
        if isinstance(self.script, list):
            resp = self.script[min(self.calls - 1, len(self.script) - 1)]
        elif callable(self.script):
            resp = self.script(messages, tools)
        else:
            resp = _default_policy(messages, tools)
        resp = Response(resp.text, list(resp.tool_calls), resp.stop_reason, Usage())
        if temperature > 0 and resp.text and not resp.tool_calls:
            resp.text = _vary(resp.text, temperature, self.rng)
        if resp.tool_calls:
            resp.stop_reason = "tool_use"
        inp = count_tokens(system or "") + sum(count_message_tokens(m) for m in messages)
        inp += sum(count_tokens(json.dumps(t)) for t in (tools or []))
        resp.usage = Usage(inp, count_tokens(resp.text) + 20 * len(resp.tool_calls))
        self.log.append({"messages": len(messages), "tools": [t["name"] for t in tools or []], "response": resp})
        return resp


_SYNONYMS = {
    "good": ["great", "fine", "solid"], "quick": ["fast", "rapid", "speedy"],
    "happy": ["glad", "pleased", "cheerful"], "big": ["large", "huge", "sizable"],
    "small": ["tiny", "little", "compact"], "says": ["states", "notes", "reports"],
}


def _vary(text: str, temperature: float, rng: random.Random) -> str:
    out = []
    for w in text.split(" "):
        key = w.lower().strip(".,!?")
        if key in _SYNONYMS and rng.random() < temperature * 0.8:
            alt = rng.choice(_SYNONYMS[key])
            w = w.replace(key, alt) if w.islower() else alt
        out.append(w)
    return " ".join(out)


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user":
            c = m["content"]
            if isinstance(c, str):
                return c
            texts = [b.get("text", "") for b in c if b.get("type") == "text"]
            if texts:
                return " ".join(texts)
    return ""


def _default_policy(messages, tools) -> Response:
    last = messages[-1] if messages else {"content": ""}
    content = last.get("content")
    if isinstance(content, list) and any(b.get("type") == "tool_result" for b in content):
        results = [str(b.get("content")) for b in content if b.get("type") == "tool_result"]
        return Response(text="Result: " + "; ".join(results))
    text = _last_user_text(messages).lower()
    for t in tools or []:
        if t["name"].lower() in text or t["name"].replace("_", " ").lower() in text:
            props = list(t.get("input_schema", {}).get("properties", {}).keys())
            args = {}
            for p in props:
                # crude argument extraction: the word after the parameter name, else the last word
                words = text.replace("?", "").split()
                args[p] = words[words.index(p) + 1] if p in words and words.index(p) + 1 < len(words) else words[-1]
            return Response(tool_calls=[ToolCall(id="call_1", name=t["name"], input=args)])
    return Response(text="I can help with that.")


class AnthropicModel(Model):
    """Calls the Anthropic Messages API. Works in CPython (urllib) and in Pyodide (sync XHR)."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5-5"):
        self.api_key = api_key
        self.model = model

    def complete(self, messages, tools=None, system=None, temperature=1.0, max_tokens=1024):
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "messages": messages, "temperature": temperature}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        data = _post(self.URL, body, {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "anthropic-dangerous-direct-browser-access": "true",
        })
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        calls = [ToolCall(b["id"], b["name"], b["input"]) for b in data["content"] if b["type"] == "tool_use"]
        u = data.get("usage", {})
        return Response(text, calls, data.get("stop_reason", "end_turn"), Usage(u.get("input_tokens", 0), u.get("output_tokens", 0)))


def _post(url: str, body: dict, headers: dict) -> dict:
    payload = json.dumps(body)
    try:
        from js import XMLHttpRequest  # type: ignore  # Pyodide only
    except ImportError:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, payload.encode(), headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read() or b'{"error": {"message": "HTTP error"}}')
    xhr = XMLHttpRequest.new()
    xhr.open("POST", url, False)
    for k, v in headers.items():
        xhr.setRequestHeader(k, v)
    xhr.send(payload)
    return json.loads(xhr.responseText)
