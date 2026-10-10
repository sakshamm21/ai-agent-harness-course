"""The agent loop: call the model, run the tools it asks for, append the results, repeat.

Everything else in nanoharness plugs into this file. Each extra is optional, so the
loop works on its own (Part 1) and gains a feature per part:
    permissions (Part 3)  hooks (Part 7)  context compaction (Part 5)
    session transcript (Part 8)  subagents through the `task` tool (Part 9)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .model import Model, ToolCall, Usage
from .tools import ToolRegistry


@dataclass
class RunResult:
    messages: list[dict]
    final_text: str
    turns: int
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end_turn"  # end_turn | max_turns | max_tokens | refusal
    tool_calls: list[dict] = field(default_factory=list)  # {"name", "input", "output", "is_error"}


def tool_result(tool_use_id: str, content: str, is_error: bool = False) -> dict:
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


class Agent:
    def __init__(self, model: Model, tools: ToolRegistry, system: str = "", permissions=None, hooks=None,
                 context=None, session=None, max_turns: int = 30, on_event: Callable[[dict], None] | None = None,
                 messages: list[dict] | None = None, depth: int = 0, subagent_model: Model | None = None,
                 subagent_max_turns: int = 15):
        self.model = model
        self.tools = tools
        self.system = system
        self.permissions = permissions  # Part 3: None means "allow everything"
        self.hooks = hooks              # Part 7
        self.context = context          # Part 5: a ContextManager, or None for no compaction
        self.session = session          # Part 8: a Session, or None for no transcript file
        self.max_turns = max_turns
        self.on_event = on_event or (lambda event: None)
        self.messages: list[dict] = list(messages or [])  # resumed transcript, if any
        self.depth = depth              # 0 = main agent, 1 = subagent
        self.subagent_model = subagent_model
        self.subagent_max_turns = subagent_max_turns
        self.child_usage = Usage()      # Part 9: tokens spent by subagents
        if context is not None and context.summarizer is None:
            context.summarizer = model

    def append(self, message: dict) -> None:
        """Add a message to the transcript, and to the session file if there is one."""
        self.messages.append(message)
        if self.session is not None:
            self.session.append(message)

    def maybe_compact(self) -> Usage:
        """Part 5 wiring: compact between rounds when the context is past its threshold."""
        if self.context is None or not self.context.should_compact(self.messages, self.system, self.tools.schemas()):
            return Usage()
        before = len(self.messages)
        self.messages = self.context.compact(self.messages)
        if self.session is not None:
            self.session.record_compaction(self.messages)
        self.on_event({"type": "compact", "before": before, "after": len(self.messages)})
        return self.context.usage or Usage()

    def run(self, prompt: str) -> RunResult:
        """Part 1: Append `prompt` as a user message, then loop up to self.max_turns times:

        1. compact if needed (self.maybe_compact(); add the usage it returns)
        2. resp = self.model.complete(self.messages, tools=self.tools.schemas(), system=self.system)
        3. add resp.usage; append resp.to_message(); emit {"type": "model", "turn", "text", "tool_calls"}
        4. no tool calls -> emit {"type": "done", ...} and return RunResult(stop_reason=resp.stop_reason)
        5. else append ONE user message holding a tool_result for every call (self.execute each)
        Out of turns -> RunResult(final_text="", stop_reason="max_turns").
        """
        self.append({"role": "user", "content": prompt})
        usage, calls = Usage(), []
        for turn in range(1, self.max_turns + 1):
            usage = usage + self.maybe_compact()
            resp = self.model.complete(self.messages, tools=self.tools.schemas(), system=self.system)
            usage = usage + resp.usage
            self.append(resp.to_message())
            self.on_event({"type": "model", "turn": turn, "text": resp.text,
                           "tool_calls": [c.name for c in resp.tool_calls]})
            if not resp.tool_calls:
                self.on_event({"type": "done", "turn": turn, "text": resp.text})
                return RunResult(self.messages, resp.text, turn, usage, resp.stop_reason, calls)
            results = [self.execute(c, calls) for c in resp.tool_calls]
            self.append({"role": "user", "content": results})  # all results in one message
        return RunResult(self.messages, "", self.max_turns, usage, "max_turns", calls)

    def execute(self, call: ToolCall, log: list[dict]) -> dict:
        """Part 1: Run one tool call and return its tool_result block. Never raise.

        Order: permissions (if set) -> pre_tool hooks (if set) -> self.tools.call ->
        post_tool hooks (if set). A denied call returns an is_error result starting
        'Permission denied'; a hook block returns one starting 'Blocked by hook'.
        Append {"name", "input", "output", "is_error"} to `log` and emit a "tool" event.
        """
        name, args = call.name, call.input
        if self.permissions is not None:
            ok, reason = self.permissions.decide(name, args)
            if not ok:
                return self._finish(call, f"Permission denied ({reason}). Do not retry this call; "
                                          "tell the user what you needed instead.", True, log)
        if self.hooks is not None:
            reason = self.hooks.run_pre(name, args)
            if reason:
                return self._finish(call, f"Blocked by hook: {reason}", True, log)
        out, is_error = self.tools.call(name, args)
        if self.hooks is not None:
            out = self.hooks.run_post(name, args, out, is_error)
        return self._finish(call, out, is_error, log)

    def _finish(self, call: ToolCall, out: str, is_error: bool, log: list[dict]) -> dict:
        log.append({"name": call.name, "input": call.input, "output": out, "is_error": is_error})
        self.on_event({"type": "tool", "name": call.name, "input": call.input, "output": out,
                       "is_error": is_error, "depth": self.depth})
        return tool_result(call.id, out, is_error)
