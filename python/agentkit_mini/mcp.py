"""A minimal MCP-style server and client over in-process JSON-RPC 2.0.

Real MCP (modelcontextprotocol.io) runs over stdio or HTTP and has more methods
(initialize, resources, prompts, notifications). The shape of tools/list and
tools/call here follows the spec, so the idea transfers directly.
"""
from __future__ import annotations

import json
from typing import Callable

from .tools import Tool


class MCPServer:
    def __init__(self, name: str):
        self.name = name
        self.tools: dict[str, Tool] = {}

    def add_tool(self, t: Tool) -> None:
        self.tools[t.name] = t

    def handle(self, request: str | dict) -> dict:
        """Handle one JSON-RPC request (as a dict or a JSON string) and return the response dict."""
        req = json.loads(request) if isinstance(request, str) else request
        rid, method, params = req.get("id"), req.get("method"), req.get("params", {})
        if method == "initialize":
            return _ok(rid, {"protocolVersion": "2025-06-18", "serverInfo": {"name": self.name}, "capabilities": {"tools": {}}})
        if method == "tools/list":
            return _ok(rid, {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                                       for t in self.tools.values()]})
        if method == "tools/call":
            t = self.tools.get(params.get("name"))
            if t is None:
                return _err(rid, -32602, f"Unknown tool: {params.get('name')}")
            try:
                out = t(**params.get("arguments", {}))
                text = out if isinstance(out, str) else json.dumps(out)
                return _ok(rid, {"content": [{"type": "text", "text": text}], "isError": False})
            except Exception as e:
                return _ok(rid, {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
        return _err(rid, -32601, f"Method not found: {method}")


class MCPClient:
    """Connects to a server (here: any object with handle()) and exposes its tools as agent Tools."""

    def __init__(self, server: MCPServer | Callable[[dict], dict]):
        self._send = server.handle if hasattr(server, "handle") else server
        self._id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        resp = self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        if "error" in resp:
            raise RuntimeError(resp["error"]["message"])
        return resp["result"]

    def list_tools(self) -> list[Tool]:
        tools = []
        for spec in self.request("tools/list")["tools"]:
            def call(_name=spec["name"], **kwargs):
                res = self.request("tools/call", {"name": _name, "arguments": kwargs})
                text = "".join(c["text"] for c in res["content"] if c["type"] == "text")
                if res.get("isError"):
                    raise RuntimeError(text)
                return text
            t = Tool(call, name=spec["name"], description=spec["description"])
            t.input_schema = spec["inputSchema"]
            tools.append(t)
        return tools


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}
