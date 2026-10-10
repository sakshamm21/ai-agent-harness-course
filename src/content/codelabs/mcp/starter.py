from agentkit_mini import MCPClient, MCPServer, MockModel, Response, ToolCall, get_model, run_loop, tool

NOTES = {
    "standup": "Standup moved to 10:15 on Thursdays, starting next week.",
    "launch": "Launch checklist: freeze the API on the 12th, docs review on the 14th.",
}


# --- The server side: an MCP server that owns the notes ---

@tool
def search_notes(query: str) -> str:
    # TODO: write a docstring (it becomes the description every MCP host shows the model),
    # then return every "title: body" line where the query appears, or "No notes match '<query>'."
    return "TODO"


@tool
def add_note(title: str, body: str) -> str:
    # TODO: write a docstring, store the note in NOTES under title.lower(), return "Saved note '<title>'."
    return "TODO"


server = MCPServer("notes")
# TODO: register both tools on the server with server.add_tool(...)

# What a host sends over the wire to discover the tools (JSON-RPC 2.0).
listing = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
print("tools/list ->", [t["name"] for t in listing["result"]["tools"]])

# --- The agent side: connect a client and hand its tools to the loop ---

client = None       # TODO: MCPClient(server)
agent_tools = []    # TODO: ask the client for the server's tools (client.list_tools())


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
