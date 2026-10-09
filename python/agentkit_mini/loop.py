"""run_loop: the agent loop in about 40 lines. Call model, run tools, append results, repeat."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .model import Model, Usage
from .tools import Tool


@dataclass
class RunResult:
    messages: list[dict]
    final_text: str
    turns: int
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end_turn"  # "end_turn" | "max_turns" | "blocked"
    tool_calls: list[dict] = field(default_factory=list)


Hook = Callable[[str, dict], object]


def run_loop(model: Model, tools: list[Tool], messages: list[dict] | str, system: str | None = None,
             max_turns: int = 10, on_event: Callable[[dict], None] | None = None,
             pre_tool: Hook | None = None, post_tool: Callable[[str, dict, object], object] | None = None,
             temperature: float = 0.0) -> RunResult:
    """Run until the model stops asking for tools, or max_turns.

    pre_tool(name, input) may return False (block the call) or a dict (replacement input).
    post_tool(name, input, result) may return a replacement result.
    on_event receives {"type": "model"|"tool"|"tool_error"|"blocked"|"done", ...} dicts.
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    messages = list(messages)
    by_name = {t.name: t for t in tools}
    emit = on_event or (lambda e: None)
    usage = Usage()
    calls: list[dict] = []

    for turn in range(1, max_turns + 1):
        resp = model.complete(messages, tools=[t.schema for t in tools] or None, system=system, temperature=temperature)
        usage = usage + resp.usage
        messages.append(resp.to_message())
        emit({"type": "model", "turn": turn, "text": resp.text, "tool_calls": [c.name for c in resp.tool_calls]})
        if not resp.tool_calls:
            emit({"type": "done", "turn": turn, "text": resp.text})
            return RunResult(messages, resp.text, turn, usage, "end_turn", calls)

        results = []
        for call in resp.tool_calls:
            args = call.input
            if pre_tool is not None:
                verdict = pre_tool(call.name, args)
                if verdict is False:
                    emit({"type": "blocked", "turn": turn, "name": call.name})
                    results.append(_result(call.id, f"Blocked by policy: {call.name} is not allowed.", True))
                    continue
                if isinstance(verdict, dict):
                    args = verdict
            fn = by_name.get(call.name)
            if fn is None:
                out, err = f"Unknown tool {call.name}. Available: {', '.join(by_name)}", True
            else:
                try:
                    out, err = fn(**args), False
                except Exception as e:  # report errors to the model, don't crash the loop
                    out, err = f"{type(e).__name__}: {e}", True
            if post_tool is not None and not err:
                replaced = post_tool(call.name, args, out)
                if replaced is not None:
                    out = replaced
            calls.append({"name": call.name, "input": args, "output": out, "error": err})
            emit({"type": "tool_error" if err else "tool", "turn": turn, "name": call.name, "input": args, "output": out})
            results.append(_result(call.id, out, err))
        messages.append({"role": "user", "content": results})

    return RunResult(messages, "", max_turns, usage, "max_turns", calls)


def _result(tool_use_id: str, out: object, is_error: bool) -> dict:
    content = out if isinstance(out, str) else json.dumps(out)
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block
