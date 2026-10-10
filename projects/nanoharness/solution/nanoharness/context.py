"""Context: count tokens, and compact the transcript by summarization at 70% of the window.

Compaction here is "simple compaction": summarize the whole conversation into one user
message and continue from that alone. Nothing old is replayed, so nothing old can go stale,
and it only ever happens between rounds (never while a tool_use waits for its result).
"""
from __future__ import annotations

import json

SUMMARY_PROMPT = """You are compacting the transcript of a coding agent so it can keep working with a fresh context.
Write a summary that lets the agent continue without the transcript. Keep:
- the user's original task, word for word
- files read or changed, and what changed in each
- commands run and their important results (test failures, errors)
- what is done, what is left, and the next step
Be specific (names, paths, line numbers). No preamble.

<transcript>
{transcript}
</transcript>"""


def count_tokens(text: str) -> int:
    """Part 5: Estimate tokens as about 4 characters per token: ceil(len(text) / 4), 0 for ''."""
    return (len(text) + 3) // 4


def count_messages(messages: list[dict], system: str = "", tools: list[dict] | None = None) -> int:
    """Part 5: Estimate the tokens of a whole request: system + tools + every message.

    String content counts as count_tokens(content); block lists count as
    count_tokens(json.dumps(block)) per block. Add 4 per message for role and framing.
    Tools count as count_tokens(json.dumps(tool)) each.
    """
    n = count_tokens(system) + sum(count_tokens(json.dumps(t)) for t in tools or [])
    for m in messages:
        c = m["content"]
        n += 4 + (count_tokens(c) if isinstance(c, str) else sum(count_tokens(json.dumps(b)) for b in c))
    return n


def render_transcript(messages: list[dict], max_block: int = 2000) -> str:
    lines = []
    for m in messages:
        blocks = [{"type": "text", "text": m["content"]}] if isinstance(m["content"], str) else m["content"]
        for b in blocks:
            t = b.get("type")
            if t == "text":
                body = b["text"]
            elif t == "tool_use":
                body = f"[tool call {b['name']}] {json.dumps(b['input'])}"
            elif t == "tool_result":
                body = f"[tool result{' ERROR' if b.get('is_error') else ''}] {b.get('content', '')}"
            else:
                continue  # thinking and other blocks are not needed for a summary
            lines.append(f"{m['role'].upper()}: {body[:max_block]}")
    return "\n".join(lines)


class ContextManager:
    def __init__(self, window: int = 16_000, threshold: float = 0.7, summarizer=None):
        self.window = window
        self.threshold = threshold
        self.summarizer = summarizer  # a Model; the agent sets it to its own model if None
        self.compactions = 0
        self.usage = None  # usage of the last summary call, so the agent can bill it

    def should_compact(self, messages: list[dict], system: str = "", tools: list[dict] | None = None) -> bool:
        """Part 5: True when the request would use >= threshold * window tokens
        and there is something to compact (more than one message)."""
        return len(messages) > 1 and count_messages(messages, system, tools) >= self.threshold * self.window

    def compact(self, messages: list[dict]) -> list[dict]:
        """Part 5: Summarize `messages` with self.summarizer and return the new transcript:
        a single user message 'This session was compacted. Summary of the work so far:\\n\\n
        {summary}\\n\\nContinue the task from here.' Increment self.compactions."""
        prompt = SUMMARY_PROMPT.format(transcript=render_transcript(messages))
        resp = self.summarizer.complete([{"role": "user", "content": prompt}], tools=None, system="")
        self.compactions += 1
        self.usage = resp.usage
        return [{"role": "user", "content": "This session was compacted. Summary of the work so far:\n\n"
                 f"{resp.text.strip()}\n\nContinue the task from here."}]
