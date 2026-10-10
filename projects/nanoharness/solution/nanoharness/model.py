"""Models: a scripted MockModel that runs offline, and AnthropicModel for real calls.

Messages use the Anthropic Messages API shape:
    {"role": "user" | "assistant", "content": str | list[block]}
Blocks: {"type": "text"}, {"type": "tool_use", "id", "name", "input"},
        {"type": "tool_result", "tool_use_id", "content", "is_error"?}
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

# $ per million tokens (input, output). Check the provider's pricing page before trusting these.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
DEFAULT_MODEL = "claude-sonnet-5-5"


def cost(input_tokens: int, output_tokens: int, model: str = DEFAULT_MODEL) -> float:
    pin, pout = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


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
    stop_reason: str = "end_turn"  # end_turn | tool_use | max_tokens | refusal
    usage: Usage = field(default_factory=Usage)
    raw_content: list[dict] | None = None  # exact blocks from the API, replayed verbatim

    def to_message(self) -> dict:
        """The assistant message to append to the transcript."""
        if self.raw_content is not None:
            return {"role": "assistant", "content": self.raw_content}
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        return {"role": "assistant", "content": blocks}


def say(text: str) -> Response:
    """A scripted final answer."""
    return Response(text=text)


_ids = iter(range(1, 10**9))


def call(name: str, text: str = "", **input) -> Response:
    """A scripted response that requests one tool call."""
    return Response(text=text, tool_calls=[ToolCall(f"toolu_{next(_ids):04d}", name, input)], stop_reason="tool_use")


def calls(*pairs: tuple[str, dict]) -> Response:
    """A scripted response that requests several tool calls in one turn."""
    return Response(tool_calls=[ToolCall(f"toolu_{next(_ids):04d}", n, i) for n, i in pairs], stop_reason="tool_use")


def _estimate(obj) -> int:
    s = obj if isinstance(obj, str) else json.dumps(obj)
    return max(1, len(s) // 4) if s else 0


class Model:
    name = "model"
    context_window = 200_000

    def complete(self, messages: list[dict], tools: list[dict] | None = None, system: str = "") -> Response:
        raise NotImplementedError


Script = Callable[[list[dict], list[dict] | None], Response]


class MockModel(Model):
    """A scripted, offline model: a list of Responses (in order; the last repeats) or a function."""

    name = "mock"

    def __init__(self, script: list[Response] | Script, context_window: int = 16_000):
        self.script = script
        self.context_window = context_window
        self.calls = 0
        self.seen: list[list[dict]] = []  # what each call was given, for tests
        self.systems: list[str] = []
        self.tool_names: list[list[str]] = []

    def complete(self, messages, tools=None, system=""):
        self.calls += 1
        self.seen.append(json.loads(json.dumps(messages)))
        self.systems.append(system)
        self.tool_names.append([t["name"] for t in tools or []])
        if callable(self.script):
            r = self.script(messages, tools)
        else:
            r = self.script[min(self.calls - 1, len(self.script) - 1)]
        usage = Usage(_estimate(system) + _estimate(messages) + _estimate(tools or []),
                      _estimate(r.text) + 20 * len(r.tool_calls))
        stop = "tool_use" if r.tool_calls else r.stop_reason
        return Response(r.text, list(r.tool_calls), stop, usage)


def _turns_since_task(messages: list[dict]) -> int:
    """How many assistant turns happened since the last plain-text user message."""
    n = 0
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            break
        n += m["role"] == "assistant"
    return n


def fixer_mock(fixes: list[dict], test_cmd: str = "python3 -m pytest -q") -> MockModel:
    """A scripted 'oracle' coding agent: look, read, edit, test, report.

    fixes: [{"path", "old", "new"}]. With no fixes it only looks around and reports.
    Used by the CLI's --mock demo and by the eval runner, so the whole harness runs offline.
    """
    def policy(messages, tools):
        if not tools:  # a compaction request: no tools offered, just summarize
            return say("Task: fix the failing tests. Progress so far: explored the repo. Next: edit and re-test.")
        step = _turns_since_task(messages)
        if step == 0:
            return call("list_dir", "Let me look at the project.", path=".")
        if step == 1 and fixes:
            return call("read_file", f"Reading {fixes[0]['path']}.", path=fixes[0]["path"])
        if step == 2 and fixes:
            return calls(*[("edit_file", {"path": f["path"], "old_string": f["old"], "new_string": f["new"]}) for f in fixes])
        if step == (3 if fixes else 1):
            return call("bash", "Running the tests.", command=test_cmd)
        last = messages[-1]["content"]
        out = last[-1].get("content", "") if isinstance(last, list) and last else ""
        lines = [ln for ln in out.strip().splitlines() if ln.strip() and not ln.startswith("[")]
        tail = lines[-1].strip("= ") if lines else "(no output)"
        if not fixes:
            return say(f"I am a scripted mock with no fix for this repo. Tests: {tail}")
        changed = ", ".join(sorted({f["path"] for f in fixes}))
        return say(f"Fixed the bug in {changed}. Tests: {tail}")

    return MockModel(policy)


class AnthropicModel(Model):
    """Calls the Anthropic Messages API with urllib (stdlib only)."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"
    context_window = 1_000_000

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None, max_tokens: int = 16000,
                 fallbacks: bool = True):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.fallbacks = fallbacks  # server-side refusal fallback ("default" routing)

    def complete(self, messages, tools=None, system=""):
        body: dict = {"model": self.model, "max_tokens": self.max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self.fallbacks:
            body["fallbacks"] = "default"
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
        req = urllib.request.Request(self.URL, json.dumps(body).encode(), headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RuntimeError(f"Anthropic API error {e.code}: {detail[:500]}") from None
        content = data.get("content", [])
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        tcs = [ToolCall(b["id"], b["name"], b["input"]) for b in content if b.get("type") == "tool_use"]
        stop = data.get("stop_reason", "end_turn")
        if stop == "refusal":
            text = text or "The model declined this request (stop_reason: refusal)."
            tcs = []
        u = data.get("usage", {})
        return Response(text, tcs, stop, Usage(u.get("input_tokens", 0), u.get("output_tokens", 0)), content)

