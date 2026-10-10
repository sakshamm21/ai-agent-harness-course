"""Part 8: a small web UI. Standard library only (http.server), so there is nothing to install.

The course plan says FastAPI; http.server does the same job here in one file with no
dependencies. Swap it for FastAPI when you need async, auth or OpenAPI docs.

Routes
  GET  /                       the single-page UI (static/index.html)
  POST /api/chat               {"conversation_id"?, "message"} -> reply JSON
  POST /api/chat?stream=1      same, but Server-Sent Events: one "data:" line per agent event
  GET  /api/traces             trace summaries, newest first
  GET  /api/traces/<id>        {"events", "timeline", "summary"} for one conversation
  GET  /api/approvals          refunds waiting for a person
  POST /api/approvals/<id>     {"decision": "approve" | "reject"}
"""
from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import guardrails
from .agent import SupportAgent, history_append
from .config import HELP_DIR, RUNS_DIR, SEED_ORDERS, STATIC_DIR
from .ingest import VectorIndex, build_index
from .model import Model, get_model
from .tools import OrderStore, ToolError
from .tracing import Tracer, list_traces, load_trace, summarize, timeline


class App:
    """Everything the handler needs: the index, the store, the models, the tracer, live histories."""

    def __init__(self, index: VectorIndex, store: OrderStore, model: Model | None = None,
                 router_model: Model | None = None, runs_dir: str | Path = RUNS_DIR):
        self.index, self.store = index, store
        self.model = model or get_model("agent")
        self.router_model = router_model or (self.model if model is not None else get_model("router"))
        self.runs_dir = Path(runs_dir)
        self.tracer = Tracer(self.runs_dir)
        self.histories: dict[str, list[dict]] = {}
        self.lock = threading.Lock()      # one SQLite connection, many request threads

    def chat(self, message: str, conversation_id: str | None = None, on_event=None) -> dict:
        conv = conversation_id or uuid.uuid4().hex[:12]
        self.tracer.path_for(conv)          # validates the id before anything is written

        def sink(e: dict) -> None:
            self.tracer(e)
            if on_event:
                on_event(guardrails.redact_value(e))

        agent = SupportAgent(self.index, self.store, self.model, self.router_model, on_event=sink)
        with self.lock:
            history = self.histories.get(conv, [])
            reply = agent.handle(message, history, conversation_id=conv)
            self.histories[conv] = history_append(history, message, reply)
        return {"conversation_id": conv, "text": reply.text, "route": reply.route, "citations": reply.citations,
                "tool_calls": [{"name": c["name"], "input": c["input"], "is_error": c["is_error"],
                                "blocked": c["blocked"]} for c in reply.tool_calls]}

    def trace(self, conversation_id: str) -> dict | None:
        path = self.tracer.path_for(conversation_id)
        if not path.exists():
            return None
        events = load_trace(path)
        return {"conversation_id": conversation_id, "events": events, "timeline": timeline(events),
                "summary": summarize(events)}

    def decide(self, approval_id: str, decision: str, approver: str = "web-ui") -> dict:
        with self.lock:
            if decision == "approve":
                return guardrails.approve_refund(self.store, approval_id, approver)
            if decision == "reject":
                return guardrails.reject_refund(self.store, approval_id, approver)
        raise ToolError("decision must be 'approve' or 'reject'")


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "supportbot/0.1"

        def log_message(self, fmt, *args):     # keep the terminal quiet; traces are the log
            pass

        def _json(self, status: int, data) -> None:
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                data = None
            return data if isinstance(data, dict) else {}

        def do_GET(self):
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            if not parts or parts == ["index.html"]:
                body = (STATIC_DIR / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parts == ["api", "traces"]:
                self._json(200, list_traces(app.runs_dir))
            elif len(parts) == 3 and parts[:2] == ["api", "traces"]:
                try:
                    t = app.trace(parts[2])
                except ValueError as e:
                    return self._json(400, {"error": str(e)})
                self._json(200, t) if t else self._json(404, {"error": "no such trace"})
            elif parts == ["api", "approvals"]:
                self._json(200, guardrails.pending_approvals(app.store))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            data = self._body()
            if parts == ["api", "chat"]:
                message = str(data.get("message", "")).strip()
                if not message:
                    return self._json(400, {"error": "message is required"})
                if parse_qs(url.query).get("stream") == ["1"]:
                    return self._stream(message, data.get("conversation_id"))
                try:
                    self._json(200, app.chat(message, data.get("conversation_id")))
                except ValueError as e:
                    self._json(400, {"error": str(e)})
            elif len(parts) == 3 and parts[:2] == ["api", "approvals"]:
                try:
                    self._json(200, app.decide(parts[2], str(data.get("decision", ""))))
                except ToolError as e:
                    self._json(400, {"error": str(e)})
            else:
                self._json(404, {"error": "not found"})

        def _stream(self, message: str, conversation_id: str | None) -> None:
            """Server-Sent Events: the browser sees route, retrieve, tool calls... as they happen."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def send(e: dict) -> None:
                self.wfile.write(f"data: {json.dumps(e)}\n\n".encode())
                self.wfile.flush()

            try:
                reply = app.chat(message, conversation_id, on_event=send)
                send({"type": "done", **reply})
            except ValueError as e:
                send({"type": "error", "error": str(e)})

    return Handler


def make_server(app: App, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(app))


def default_app() -> App:
    """The real thing: help center index, a store that persists in runs/store.db, env-chosen models."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return App(build_index(HELP_DIR), OrderStore(RUNS_DIR / "store.db", seed=SEED_ORDERS))


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = default_app()
    httpd = make_server(app, host, port)
    print(f"supportbot on http://{host}:{port}  (model: {app.model.name}, traces: {app.tracer.dir})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
