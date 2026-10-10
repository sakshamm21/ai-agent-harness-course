"""Project instructions: load AGENTS.md from the working dir and assemble the system prompt.

The system prompt is built once per session and then frozen. Changing it mid-session
would throw away the prompt cache and confuse the model about which rules apply.
"""
from __future__ import annotations

import os
import platform

INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")  # first one found wins
MAX_INSTRUCTIONS = 20_000  # characters

BASE_PROMPT = """You are nanoharness, a coding agent working in a local repository.
You act through tools: read files before editing them, make small exact edits with edit_file,
and run the tests with bash to check your work. Never guess file contents.
When the task is done (or you are blocked), stop calling tools and reply with a short summary
of what you changed and how you verified it. If a tool call is denied, do not retry it; explain
what you needed instead."""


def load_instructions(workdir: str) -> str | None:
    """Part 6: Return the text of the first file in INSTRUCTION_FILES that exists in workdir,
    or None. If it is longer than MAX_INSTRUCTIONS characters, cut it there and append
    '\\n[... instructions truncated ...]'."""
    for name in INSTRUCTION_FILES:
        path = os.path.join(workdir, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if len(text) > MAX_INSTRUCTIONS:
                text = text[:MAX_INSTRUCTIONS] + "\n[... instructions truncated ...]"
            return text
    return None


def build_system_prompt(workdir: str, instructions: str | None = None, extra: str = "") -> str:
    """Part 6: BASE_PROMPT, then an environment section, then the project instructions.

    Layout (sections separated by a blank line):
        BASE_PROMPT
        <env>\\nWorking directory: {workdir}\\nPlatform: {platform.system()}\\n</env>
        <project_instructions source="AGENTS.md">\\n{instructions}\\n</project_instructions>   (only if any)
        extra   (only if non-empty)
    """
    parts = [BASE_PROMPT, f"<env>\nWorking directory: {workdir}\nPlatform: {platform.system()}\n</env>"]
    if instructions:
        parts.append(f'<project_instructions source="AGENTS.md">\n{instructions.strip()}\n</project_instructions>')
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)
