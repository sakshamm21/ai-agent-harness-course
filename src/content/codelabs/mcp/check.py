# Runs after the learner's code, in the same namespace. Use check(label, condition, hint).
_list = server.handle({"jsonrpc": "2.0", "id": 101, "method": "tools/list"})
_specs = {t["name"]: t for t in _list.get("result", {}).get("tools", [])}
check("the server lists search_notes and add_note", set(_specs) == {"search_notes", "add_note"},
      "Register both tools with server.add_tool(search_notes) and server.add_tool(add_note).")
check("every listed tool has a real description", _specs and all(len(t["description"]) >= 30 for t in _specs.values()),
      "Write a docstring for each tool: what it does and when to use it. Hosts show it to the model as is.")
check("add_note's schema requires title and body", set(_specs.get("add_note", {}).get("inputSchema", {}).get("required", [])) == {"title", "body"})
_call = server.handle({"jsonrpc": "2.0", "id": 102, "method": "tools/call", "params": {"name": "search_notes", "arguments": {"query": "standup"}}})
_text = "".join(c.get("text", "") for c in _call.get("result", {}).get("content", []))
check("tools/call search_notes finds the standup note", "10:15" in _text,
      "search_notes should return every 'title: body' line whose title or body contains the query.")
_miss = server.handle({"jsonrpc": "2.0", "id": 103, "method": "tools/call", "params": {"name": "search_notes", "arguments": {"query": "zebra"}}})
check("a search with no hits says so", "no notes" in "".join(c.get("text", "") for c in _miss.get("result", {}).get("content", [])).lower())
_names = sorted(t.name for t in agent_tools) if agent_tools else []
check("the agent's tools come from the MCP client", client is not None and _names == ["add_note", "search_notes"],
      "client = MCPClient(server), then agent_tools = client.list_tools().")
if client is not None and _names:
    _by = {t.name: t for t in agent_tools}
    _by["add_note"](title="Offsite", body="Offsite is in Porto on May 20.")
    _found = _by["search_notes"](query="porto")
else:
    _found = ""
check("a note added through the client can be found again", "porto" in _found.lower(),
      "add_note should store NOTES[title.lower()] = body.")
check("the agent's final answer mentions 10:15", "10:15" in result.final_text)
