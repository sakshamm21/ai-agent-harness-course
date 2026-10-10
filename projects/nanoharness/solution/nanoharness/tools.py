"""Tools: the six things a coding agent can do, plus the registry that dispatches calls.

Every tool returns a string. Errors are raised as exceptions; the registry turns them
into is_error tool results so the model can read the message and try again.
"""
from __future__ import annotations

import fnmatch
import functools
import json
import os
import re
from dataclasses import dataclass
from typing import Callable

IGNORED_DIRS = {".git", "__pycache__", ".nanoharness", ".pytest_cache", "node_modules", ".venv"}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., str]

    @property
    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None):
        self.tools: dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def without(self, *names: str) -> "ToolRegistry":
        return ToolRegistry([t for n, t in self.tools.items() if n not in names])

    def schemas(self) -> list[dict]:
        return [t.schema for t in self.tools.values()]

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Part 1: Run tool `name` with `args`. Return (output, is_error). Never raise.

        Unknown tool -> an error that lists the available tools. Any exception the tool
        raises -> (f"{ExceptionType}: {message}", True). Non-string output -> json.dumps.
        """
        tool = self.tools.get(name)
        if tool is None:
            return f"Unknown tool '{name}'. Available tools: {', '.join(self.tools)}", True
        try:
            out = tool.fn(**args)
        except Exception as e:  # report errors to the model, don't crash the loop
            return f"{type(e).__name__}: {e}", True
        return (out if isinstance(out, str) else json.dumps(out)), False


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


S = {"type": "string"}
I = {"type": "integer"}


def resolve_path(root: str, path: str) -> str:
    """Part 2: Resolve `path` (relative to `root`, or absolute) to a real absolute path.

    Raise PermissionError if the result is outside `root`: the agent may only touch
    files inside its working directory. Resolve symlinks (os.path.realpath) before checking.
    """
    root_real = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root_real, os.path.expanduser(path)))
    if full != root_real and not full.startswith(root_real + os.sep):
        raise PermissionError(f"{path} is outside the working directory {root_real}")
    return full


def read_file(root: str, path: str, offset: int = 1, limit: int = 2000) -> str:
    """Part 2: Return lines offset..offset+limit-1 of the file, each prefixed '{n:>5}\\t'.

    Append a note like '[... 120 more lines; use offset=2001 ...]' when there is more.
    """
    full = resolve_path(root, path)
    with open(full, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    start = max(1, offset)
    chunk = lines[start - 1:start - 1 + limit]
    out = "\n".join(f"{n:>5}\t{line}" for n, line in enumerate(chunk, start))
    rest = len(lines) - (start - 1 + len(chunk))
    if rest > 0:
        out += f"\n[... {rest} more lines; use offset={start + len(chunk)} ...]"
    return out or "(empty file)"


def write_file(root: str, path: str, content: str) -> str:
    """Part 2: Write `content` to the file (creating parent directories). Return a short receipt."""
    full = resolve_path(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} characters to {path}"


def edit_file(root: str, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Part 2: Replace `old_string` with `new_string` in the file, by exact string match.

    old_string must occur exactly once unless replace_all is true. Raise ValueError with a
    message that tells the model how to fix its call when it is missing or ambiguous.
    """
    full = resolve_path(root, path)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    n = text.count(old_string)
    if not old_string or n == 0:
        raise ValueError(f"old_string not found in {path}. Read the file and copy the exact text, "
                         "including indentation, without the line-number prefix.")
    if n > 1 and not replace_all:
        raise ValueError(f"old_string appears {n} times in {path}. Include more surrounding lines "
                         "to make it unique, or set replace_all to true.")
    with open(full, "w", encoding="utf-8") as f:
        f.write(text.replace(old_string, new_string))
    return f"Edited {path}: replaced {n if replace_all else 1} occurrence(s)."


def list_dir(root: str, path: str = ".") -> str:
    """Part 2: List a directory: one entry per line, sorted, directories end with '/'.

    Skip IGNORED_DIRS. Return '(empty directory)' when there is nothing to show.
    """
    full = resolve_path(root, path)
    names = []
    for name in sorted(os.listdir(full)):
        if name in IGNORED_DIRS:
            continue
        names.append(name + "/" if os.path.isdir(os.path.join(full, name)) else name)
    return "\n".join(names) or "(empty directory)"


def grep(root: str, pattern: str, path: str = ".", glob: str = "*", max_matches: int = 100) -> str:
    """Part 2: Search files under `path` for the regex `pattern`.

    Return 'relpath:lineno: line' per match (relative to root), at most max_matches,
    skipping IGNORED_DIRS and files that don't match `glob`. Return 'No matches.' if none.
    """
    rx = re.compile(pattern)
    base = resolve_path(root, path)
    root_real = os.path.realpath(root)
    files = [base] if os.path.isfile(base) else []
    for d, dirs, fs in os.walk(base):
        dirs[:] = sorted(x for x in dirs if x not in IGNORED_DIRS)
        files += [os.path.join(d, f) for f in sorted(fs) if fnmatch.fnmatch(f, glob)]
    hits = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if rx.search(line):
                        hits.append(f"{os.path.relpath(fp, root_real)}:{n}: {line.rstrip()}")
                        if len(hits) >= max_matches:
                            return "\n".join(hits) + f"\n[stopped at {max_matches} matches]"
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable file
    return "\n".join(hits) or "No matches."


def file_tools(root: str) -> list[Tool]:
    """The five file tools, bound to one working directory."""
    p = functools.partial
    return [
        Tool("read_file", "Read a text file. Lines come back numbered ('   12\\tcode'); the number and tab are "
             "not part of the file. Use offset/limit for long files.",
             _schema({"path": S, "offset": I, "limit": I}, ["path"]), p(read_file, root)),
        Tool("write_file", "Create or overwrite a file with the given content. Prefer edit_file for changes "
             "to an existing file.", _schema({"path": S, "content": S}, ["path", "content"]), p(write_file, root)),
        Tool("edit_file", "Replace an exact string in a file. old_string must match the file exactly (copy it "
             "from read_file without line numbers) and be unique unless replace_all is true.",
             _schema({"path": S, "old_string": S, "new_string": S, "replace_all": {"type": "boolean"}},
                     ["path", "old_string", "new_string"]), p(edit_file, root)),
        Tool("list_dir", "List the files and folders in a directory (default: the working directory).",
             _schema({"path": S}, []), p(list_dir, root)),
        Tool("grep", "Search file contents with a regular expression. Returns path:line: text for each match. "
             "Use glob (e.g. '*.py') to filter file names.",
             _schema({"pattern": S, "path": S, "glob": S}, ["pattern"]), p(grep, root)),
    ]


def bash_tool(sandbox) -> Tool:
    return Tool("bash", "Run a shell command in the working directory and return its output and exit code. "
                "Use it to run tests, git, or scripts. Commands time out; avoid interactive programs.",
                _schema({"command": S}, ["command"]), lambda command: sandbox.run(command))
