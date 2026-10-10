"""run_loop: the agent loop. Call the model, run the tools it asks for, append results, repeat."""
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
    stop_reason: str = "end_turn"  # "end_turn" | "max_turns"
    tool_calls: list[dict] = field(default_factory=list)


def run_loop(model: Model, tools: list[Tool], messages: list[dict] | str, system: str | None = None,
             max_turns: int = 8, on_event: Callable[[dict], None] | None = None,
             temperature: float = 0.0) -> RunResult:
    """Run until the model stops asking for tools, or max_turns.

    Tool errors are sent back to the model as is_error tool results. Exceptions
    raised by the model call itself (including BudgetExceeded) propagate.
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
            return RunResult(messages, resp.text, turn, usage, "end_turn", calls)

        results = []
        for call in resp.tool_calls:
            fn = by_name.get(call.name)
            if fn is None:
                out, err = f"Unknown tool {call.name}. Available: {', '.join(by_name)}", True
            else:
                try:
                    out, err = fn(**call.input), False
                except Exception as e:  # report tool errors to the model, don't crash the loop
                    out, err = f"{type(e).__name__}: {e}", True
            calls.append({"name": call.name, "input": call.input, "output": out, "error": err})
            emit({"type": "tool_error" if err else "tool", "turn": turn, "name": call.name, "input": call.input})
            content = out if isinstance(out, str) else json.dumps(out)
            block = {"type": "tool_result", "tool_use_id": call.id, "content": content}
            if err:
                block["is_error"] = True
            results.append(block)
        messages.append({"role": "user", "content": results})

    return RunResult(messages, "", max_turns, usage, "max_turns", calls)
