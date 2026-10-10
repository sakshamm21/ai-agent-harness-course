"""Part 8: traces. One JSONL file per conversation, one event per line, read back as a timeline.

The agent already emits events (user_message, route, retrieve, model_call, tool_call,
blocked, redacted, final...). The Tracer appends each one to runs/traces/<id>.jsonl,
redacted, the moment it happens. The viewer turns a file back into rows on a time axis.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import RUNS_DIR
from .guardrails import redact_value

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ERROR_TYPES = {"blocked", "max_turns", "invalid_citations"}


class Tracer:
    """Callable sink for agent events: SupportAgent(on_event=Tracer())."""

    def __init__(self, runs_dir: str | Path = RUNS_DIR, redact: bool = True):
        self.dir = Path(runs_dir) / "traces"
        self.redact = redact

    def path_for(self, conversation_id: str) -> Path:
        if not SAFE_ID.match(conversation_id):
            raise ValueError(f"bad conversation id {conversation_id!r}")
        return self.dir / f"{conversation_id}.jsonl"

    def write(self, event: dict) -> None:
        """Append one event as one JSON line. Redact first: traces outlive conversations."""
        self.dir.mkdir(parents=True, exist_ok=True)
        if self.redact:
            event = redact_value(event)
        with self.path_for(event["conversation_id"]).open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    __call__ = write


def load_trace(path: str | Path) -> list[dict]:
    """Every event in a JSONL file. A torn or corrupt line is skipped, not fatal."""
    events = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and "type" in e:
            events.append(e)
    return events


def list_traces(runs_dir: str | Path = RUNS_DIR) -> list[dict]:
    """One summary row per trace file, newest first."""
    rows = []
    for p in (Path(runs_dir) / "traces").glob("*.jsonl"):
        events = load_trace(p)
        if not events:
            continue
        first = next((e.get("text", "") for e in events if e["type"] == "user_message"), "")
        rows.append({"conversation_id": p.stem, "started": events[0].get("ts", 0), "events": len(events),
                     "first_message": first[:80], **summarize(events)})
    return sorted(rows, key=lambda r: -r["started"])


def _label(e: dict) -> str:
    t = e["type"]
    if t == "user_message" or t == "final":
        return e.get("text", "")[:120]
    if t == "route":
        return f"{e.get('label')} (by {e.get('source')})"
    if t == "retrieve":
        return ", ".join(f"{h['article_id']} {h['score']:.2f}" for h in e.get("hits", [])) or "no documents"
    if t == "model_call":
        calls = e.get("tool_calls") or []
        return f"turn {e.get('turn')}: " + (f"asks for {', '.join(calls)}" if calls else "answers")
    if t == "tool_call":
        return f"{e.get('name')}({json.dumps(e.get('input', {}))})"
    if t == "blocked":
        return f"{e.get('name')} blocked: {e.get('reason')}"
    if t == "suspicious_document":
        return f"{e.get('article_id')}: {', '.join(e.get('signals', []))}"
    if t == "redacted":
        return ", ".join(f"{k} x{v}" for k, v in e.get("counts", {}).items())
    return json.dumps({k: v for k, v in e.items() if k not in ("ts", "conversation_id", "type")})[:120]


def timeline(events: list[dict]) -> list[dict]:
    """Rows for the viewer: {"t_ms", "type", "label", "duration_ms", "status"}, one per event.

    t_ms is milliseconds since the first event's ts. label comes from _label(e). status is
    "error" for ERROR_TYPES and failed tool calls, "warn" for suspicious_document and
    redacted, otherwise "ok".
    """
    if not events:
        return []
    t0 = events[0].get("ts", 0)
    rows = []
    for e in events:
        if e["type"] in ERROR_TYPES or (e["type"] == "tool_call" and e.get("is_error")):
            status = "error"
        elif e["type"] in ("suspicious_document", "redacted"):
            status = "warn"
        else:
            status = "ok"
        rows.append({"t_ms": round((e.get("ts", t0) - t0) * 1000, 1), "type": e["type"], "label": _label(e),
                     "duration_ms": e.get("duration_ms", 0), "status": status})
    return rows


def summarize(events: list[dict]) -> dict:
    """Counts and totals for the header of a trace.

    Keys: turns (user_message events), model_calls, tool_calls, blocked, input_tokens and
    output_tokens (summed over model_call events), duration_ms (first to last event),
    routes (route labels in order), last_reply (the last final event's text, 120 chars).
    """
    count = lambda t: sum(e["type"] == t for e in events)   # noqa: E731
    finals = [e for e in events if e["type"] == "final"]
    return {
        "turns": count("user_message"),
        "model_calls": count("model_call"),
        "tool_calls": count("tool_call"),
        "blocked": count("blocked"),
        "input_tokens": sum(e.get("input_tokens", 0) for e in events if e["type"] == "model_call"),
        "output_tokens": sum(e.get("output_tokens", 0) for e in events if e["type"] == "model_call"),
        "duration_ms": round((events[-1].get("ts", 0) - events[0].get("ts", 0)) * 1000, 1) if events else 0,
        "routes": [e.get("label") for e in events if e["type"] == "route"],
        "last_reply": finals[-1].get("text", "")[:120] if finals else "",
    }
