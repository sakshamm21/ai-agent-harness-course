---
title: "Model Context Protocol (MCP)"
---

## The scenario

Your team keeps its notes in a small service. You want any agent (yours, Claude Code, a desktop assistant) to be able to search them, without writing a new integration for each one. So you wrap the notes in an **MCP server**, and connect your agent to it through an **MCP client**.

`agentkit_mini` has a tiny in-process version of both. The messages are real JSON-RPC 2.0 with the same `tools/list` and `tools/call` methods as the MCP spec; only the transport (stdio or HTTP in real MCP) is replaced by a function call.

## Your task

1. Finish `search_notes(query)`: return every `"title: body"` line whose title or body contains the query (case-insensitive), joined by newlines, or `"No notes match '<query>'."`.
2. Finish `add_note(title, body)`: store the note under `title.lower()` and return `"Saved note '<title>'."`.
3. Give both tools a docstring that says what they do and when to use them. The server sends it as the tool's `description`.
4. Register both tools on the server with `server.add_tool(...)`. Press **Run**: the `tools/list` line should show both names.
5. Connect the agent: `client = MCPClient(server)`, then `agent_tools = client.list_tools()`. The loop now calls the server's tools without knowing how they are implemented.

Press **Run** to see the agent answer, then **Check**.

## What the checks look for

- A raw `tools/list` request returns exactly `search_notes` and `add_note`, each with a description of 30+ characters, and `add_note` requires `title` and `body`.
- A raw `tools/call` for `search_notes` with `"standup"` returns the 10:15 note, and a query with no hits says so.
- `agent_tools` came from the client, and a note added through it can be searched.
- The agent's final answer mentions 10:15.
