"""Hooks: your code runs before and after every tool call, configured in nanoharness.json.

    {"hooks": {
        "pre_tool":  [{"matcher": "bash", "command": "python3 .hooks/guard.py"}],
        "post_tool": [{"matcher": "edit_file|write_file", "command": "ruff check --quiet ."}]}}

A hook command gets the event as JSON on stdin: {"event", "tool", "input", "output"?}.
pre_tool: exit code 2 blocks the call; stderr (or stdout) is the reason the model sees.
post_tool: anything printed on stdout is appended to the tool result.
Python callables work too (Hooks.pre / Hooks.post lists), handy for tests and embedding.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Callable

CONFIG_FILES = ("nanoharness.json", "nanoharness.toml")
BLOCK_EXIT_CODE = 2


def load_config(workdir: str, path: str | None = None) -> dict:
    """Part 7: Load the config dict from `path`, or from the first of CONFIG_FILES found in
    workdir. .json is parsed with json; .toml with tomllib (Python 3.11+). Return {} if none."""
    candidates = [path] if path else [os.path.join(workdir, n) for n in CONFIG_FILES]
    for p in candidates:
        if p and os.path.isfile(p):
            if p.endswith(".toml"):
                import tomllib  # Python 3.11+; use nanoharness.json on 3.10
                with open(p, "rb") as f:
                    return tomllib.load(f)
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return {}


def run_hook_command(command: str, payload: dict, cwd: str, timeout: float = 30) -> tuple[int, str, str]:
    """Part 7: Run `command` with the shell in `cwd`, payload as JSON on stdin.
    Return (exit_code, stdout, stderr). A timeout counts as exit code 1 with a message."""
    try:
        p = subprocess.run(command, shell=True, cwd=cwd, input=json.dumps(payload), capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"hook timed out after {timeout}s: {command}"


class Hooks:
    def __init__(self, pre: list[dict] | None = None, post: list[dict] | None = None, cwd: str = "."):
        # each entry: {"matcher": regex, "command": str} or {"matcher": regex, "fn": callable}
        self.pre = list(pre or [])
        self.post = list(post or [])
        self.cwd = cwd
        self.warnings: list[str] = []

    @classmethod
    def from_config(cls, cfg: dict, cwd: str) -> "Hooks":
        h = cfg.get("hooks", {})
        return cls(h.get("pre_tool", []), h.get("post_tool", []), cwd)

    def add_pre(self, fn: Callable[[str, dict], str | None], matcher: str = ".*") -> None:
        self.pre.append({"matcher": matcher, "fn": fn})

    def add_post(self, fn: Callable[[str, dict, str, bool], str | None], matcher: str = ".*") -> None:
        self.post.append({"matcher": matcher, "fn": fn})

    @staticmethod
    def _matches(hook: dict, tool: str) -> bool:
        return re.fullmatch(hook.get("matcher", ".*") or ".*", tool) is not None

    def run_pre(self, tool: str, args: dict) -> str | None:
        """Part 7: Run every matching pre_tool hook in order. Return a block reason (str) from
        the first hook that blocks, or None to let the call through.

        fn hooks block by returning a non-empty string. Command hooks block with exit code
        BLOCK_EXIT_CODE; the reason is stderr, else stdout, else 'blocked by hook <command>'.
        Other non-zero exit codes do not block: record a warning in self.warnings.
        """
        for h in self.pre:
            if not self._matches(h, tool):
                continue
            if "fn" in h:
                reason = h["fn"](tool, args)
                if reason:
                    return str(reason)
                continue
            code, out, err = run_hook_command(h["command"], {"event": "pre_tool", "tool": tool, "input": args},
                                              self.cwd)
            if code == BLOCK_EXIT_CODE:
                return (err.strip() or out.strip() or f"blocked by hook {h['command']}")
            if code != 0:
                self.warnings.append(f"pre_tool hook {h['command']!r} exited {code}: {err.strip()}")
        return None

    def run_post(self, tool: str, args: dict, output: str, is_error: bool) -> str:
        """Part 7: Run every matching post_tool hook and return the (possibly extended) output.

        fn hooks may return a string to append. Command hooks get {"event": "post_tool", "tool",
        "input", "output", "is_error"} on stdin; non-empty stdout is appended as
        '\\n[hook] <stdout>'.
        """
        for h in self.post:
            if not self._matches(h, tool):
                continue
            if "fn" in h:
                note = h["fn"](tool, args, output, is_error)
            else:
                payload = {"event": "post_tool", "tool": tool, "input": args, "output": output, "is_error": is_error}
                code, note, err = run_hook_command(h["command"], payload, self.cwd)
                if code != 0:
                    self.warnings.append(f"post_tool hook {h['command']!r} exited {code}: {err.strip()}")
            if note and note.strip():
                output += f"\n[hook] {note.strip()}"
        return output
