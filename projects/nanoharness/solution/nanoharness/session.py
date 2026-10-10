"""Sessions: save the transcript as JSONL, one event per line, and resume from it.

    {"type": "meta", "id", "created", "model", "workdir"}
    {"type": "message", "message": {...}}          appended for every message
    {"type": "compact", "messages": [...]}          the transcript after a compaction

Append-only means a crash loses at most the line being written, and replaying the file
rebuilds exactly the transcript the model last saw.
"""
from __future__ import annotations

import glob
import json
import os
import secrets
import time

SESSION_DIR = os.path.join(".nanoharness", "sessions")


def new_session_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


class Session:
    def __init__(self, path: str):
        self.path = path
        self.id = os.path.basename(path).removesuffix(".jsonl")

    @classmethod
    def create(cls, workdir: str, model: str = "", session_id: str | None = None) -> "Session":
        d = os.path.join(workdir, SESSION_DIR)
        os.makedirs(d, exist_ok=True)
        s = cls(os.path.join(d, f"{session_id or new_session_id()}.jsonl"))
        s.write({"type": "meta", "id": s.id, "created": time.time(), "model": model, "workdir": workdir})
        return s

    def write(self, event: dict) -> None:
        """Part 8: Append `event` as one JSON line (json.dumps + '\\n') and flush it to disk."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()

    def append(self, message: dict) -> None:
        self.write({"type": "message", "message": message})

    def record_compaction(self, messages: list[dict]) -> None:
        self.write({"type": "compact", "messages": messages})

    def load(self) -> list[dict]:
        """Part 8: Replay the file and return the current transcript.

        "message" events append their message; "compact" events replace the whole list;
        other events are skipped. Ignore a final line that is not valid JSON (a crash
        mid-write). Then return repair_transcript(messages).
        """
        messages: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue  # half-written last line
                if ev.get("type") == "message":
                    messages.append(ev["message"])
                elif ev.get("type") == "compact":
                    messages = list(ev["messages"])
        return repair_transcript(messages)


def repair_transcript(messages: list[dict]) -> list[dict]:
    """Part 8: If the last message is an assistant turn with tool_use blocks (the run stopped
    before their results were saved), append a user message with one tool_result per call:
    content 'Interrupted: the session ended before this tool ran.', is_error True.
    The API rejects a tool_use without a matching tool_result."""
    if messages and messages[-1]["role"] == "assistant" and isinstance(messages[-1]["content"], list):
        pending = [b for b in messages[-1]["content"] if b.get("type") == "tool_use"]
        if pending:
            messages = messages + [{"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b["id"], "is_error": True,
                 "content": "Interrupted: the session ended before this tool ran."} for b in pending]}]
    return messages


def find_session(workdir: str, session_id: str | None = None) -> Session | None:
    """The named session, or the most recently modified one in workdir."""
    d = os.path.join(workdir, SESSION_DIR)
    if session_id:
        p = os.path.join(d, f"{session_id}.jsonl")
        return Session(p) if os.path.isfile(p) else None
    files = sorted(glob.glob(os.path.join(d, "*.jsonl")), key=os.path.getmtime)
    return Session(files[-1]) if files else None
