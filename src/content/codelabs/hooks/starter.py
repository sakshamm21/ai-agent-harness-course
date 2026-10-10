from agentkit_mini import MockModel, Response, ToolCall, tool, run_loop

# A tiny in-memory repo. The model edits it through write_file.
FILES = {
    ".env": "STRIPE_KEY=sk_live_51H8xQ2",
    "app.py": "def total(xs):\n    return sum(xs)\n",
}


@tool
def write_file(path: str, content: str) -> str:
    """Writes text to a file in the repo, replacing what was there."""
    FILES[path] = content
    return f"Wrote {len(content)} chars to {path}"


def fmt(src: str) -> str:
    """A toy formatter: tabs become 4 spaces, trailing spaces go, file ends with one newline."""
    lines = [line.replace("\t", "    ").rstrip() for line in src.split("\n")]
    return "\n".join(lines).rstrip("\n") + "\n"


AUDIT = []  # every tool call the harness saw, in order


def pre_tool(name, args):
    """Runs before every tool call. Return False to block it."""
    AUDIT.append((name, args.get("path")))
    # TODO: block write_file when the file name is .env or starts with ".env."
    #       (".env", "config/.env.local"), but not "docs/environment.md".
    return None


def post_tool(name, args, result):
    """Runs after every successful tool call. Return a new result, or None to keep it."""
    # TODO: after write_file on a .py file, run fmt() on FILES[path] and save it back.
    #       Return the result with " (auto-formatted)" added so the model knows.
    return None


# A scripted model that makes four writes, then answers.
model = MockModel([
    Response(tool_calls=[ToolCall("c1", "write_file", {"path": ".env", "content": "STRIPE_KEY=sk_test_000"})]),
    Response(tool_calls=[ToolCall("c2", "write_file", {"path": "app.py", "content": "def total(xs):\n\treturn sum(xs)   \n\n\n"})]),
    Response(tool_calls=[ToolCall("c3", "write_file", {"path": "config/.env.local", "content": "DEBUG=1"})]),
    Response(tool_calls=[ToolCall("c4", "write_file", {"path": "docs/environment.md", "content": "# Environment\nSee .env.example.\n"})]),
    Response(text="Updated the config, app.py and the docs."),
])

events = []
result = run_loop(model, [write_file], "Switch the app to test keys and tidy up app.py.",
                  pre_tool=pre_tool, post_tool=post_tool, on_event=events.append)

for e in events:
    if e["type"] == "blocked":
        print("blocked ", e["name"])
    elif e["type"] in ("tool", "tool_error"):
        print(e["type"].ljust(8), e["name"], e["input"].get("path"), "->", e["output"])
print("\n.env is now:", FILES[".env"])
print("app.py is now:", repr(FILES["app.py"]))
print("Audit log:", AUDIT)
