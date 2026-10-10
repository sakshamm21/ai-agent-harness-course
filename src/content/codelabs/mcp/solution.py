from agentkit_mini import MCPClient, MCPServer, MockModel, Response, ToolCall, get_model, run_loop, tool

NOTES = {
    "standup": "Standup moved to 10:15 on Thursdays, starting next week.",
    "launch": "Launch checklist: freeze the API on the 12th, docs review on the 14th.",
}


# --- The server side: an MCP server that owns the notes ---

@tool
def search_notes(query: str) -> str:
    """Searches the team's notes by keyword and returns every note that matches. Use it before answering questions about meetings, plans or decisions."""
    q = query.lower()
    hits = [f"{title}: {body}" for title, body in NOTES.items() if q in title or q in body.lower()]
    return "\n".join(hits) if hits else f"No notes match '{query}'."


@tool
def add_note(title: str, body: str) -> str:
    """Saves a new note under a short title. Use it only when the user asks you to remember or write something down."""
    NOTES[title.lower()] = body
    return f"Saved note '{title}'."


server = MCPServer("notes")
server.add_tool(search_notes)
server.add_tool(add_note)

# What a host sends over the wire to discover the tools (JSON-RPC 2.0).
listing = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
print("tools/list ->", [t["name"] for t in listing["result"]["tools"]])

# --- The agent side: connect a client and hand its tools to the loop ---

client = MCPClient(server)
agent_tools = client.list_tools()


def script(messages, tools):
    names = [t["name"] for t in tools or []]
    last = messages[-1]["content"]
    if isinstance(last, list) and last and last[0].get("type") == "tool_result":
        return Response(text="From your notes: " + last[0]["content"])
    if "search_notes" in names:
        return Response(tool_calls=[ToolCall("call_1", "search_notes", {"query": "standup"})])
    return Response(text="I don't have any way to read your notes.")


model = get_model(MockModel(script))
result = run_loop(model, agent_tools, "When is standup on Thursday?", max_turns=4)
print("Final answer:", result.final_text)
