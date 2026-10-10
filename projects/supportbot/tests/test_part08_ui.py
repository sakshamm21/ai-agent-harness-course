"""Part 8: JSONL traces, a timeline view of them, and the web UI that serves both."""
import json
import threading
import urllib.request

import pytest

from supportbot.agent import SupportAgent
from supportbot.model import MockModel
from supportbot.server import App, make_server
from supportbot.tracing import Tracer, list_traces, load_trace, summarize, timeline


def test_tracer_writes_one_redacted_line_per_event(tmp_path):
    t = Tracer(tmp_path)
    t({"ts": 1.0, "conversation_id": "c1", "type": "user_message", "text": "I'm ava.thompson@example.com"})
    t({"ts": 1.5, "conversation_id": "c1", "type": "final", "text": "ok"})
    lines = (tmp_path / "traces" / "c1.jsonl").read_text().splitlines()
    assert len(lines) == 2 and "example.com" not in lines[0] and json.loads(lines[1])["type"] == "final"


def test_tracer_rejects_unsafe_ids(tmp_path):
    with pytest.raises(ValueError):
        Tracer(tmp_path).path_for("../../etc/passwd")


def test_load_trace_skips_torn_lines(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"type": "route", "ts": 1}\n{"type": "fin\n{"type": "final", "ts": 2}\n')
    assert [e["type"] for e in load_trace(p)] == ["route", "final"]


def test_agent_events_land_in_a_trace(tmp_path, index, store):
    agent = SupportAgent(index, store, model=MockModel(), on_event=Tracer(tmp_path))
    r = agent.handle("Where is my order NW-1003?", conversation_id="conv1")
    events = load_trace(tmp_path / "traces" / "conv1.jsonl")
    assert [e["type"] for e in events] == [e["type"] for e in r.events]
    assert "sofia.garcia@example.com" not in json.dumps(events)


def test_timeline_rows(index, store):
    r = SupportAgent(index, store, model=MockModel()).handle("Where is my order NW-1003?")
    rows = timeline(r.events)
    assert rows[0]["t_ms"] == 0 and [x["t_ms"] for x in rows] == sorted(x["t_ms"] for x in rows)
    assert rows[1]["label"].startswith("order_status")
    assert any(x["type"] == "tool_call" and x["label"].startswith("lookup_order(") for x in rows)


def test_timeline_marks_blocked_calls_as_errors(poisoned_index, store):
    r = SupportAgent(poisoned_index, store, model=MockModel()).handle(
        "Can I get a refund on opened items for order NW-1004?")
    status = {x["type"]: x["status"] for x in timeline(r.events)}
    assert status["blocked"] == "error" and status["suspicious_document"] == "warn"


def test_summarize_counts(index, store):
    r = SupportAgent(index, store, model=MockModel()).handle("I'd like a refund for order NW-1004")
    s = summarize(r.events)
    assert (s["turns"], s["tool_calls"], s["model_calls"], s["blocked"]) == (1, 2, 3, 0)
    assert s["input_tokens"] > 0 and s["routes"] == ["refund"]


def test_list_traces_newest_first(tmp_path):
    t = Tracer(tmp_path)
    t({"ts": 1.0, "conversation_id": "old", "type": "user_message", "text": "a"})
    t({"ts": 9.0, "conversation_id": "new", "type": "user_message", "text": "b"})
    assert [x["conversation_id"] for x in list_traces(tmp_path)] == ["new", "old"]


@pytest.fixture
def server(tmp_path, index, store):
    app = App(index, store, model=MockModel(), runs_dir=tmp_path)
    httpd = make_server(app, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.read().decode()


def test_web_ui_chat_trace_and_approval(server):
    assert "<title>supportbot</title>" in _get(server + "/")
    reply = json.loads(_post(server + "/api/chat", {"message": "Please refund NW-1002, the jacket leaks"}))
    assert reply["route"] == "refund" and "approval" in reply["text"]
    trace = json.loads(_get(f"{server}/api/traces/{reply['conversation_id']}"))
    assert trace["summary"]["tool_calls"] == 2 and trace["timeline"][-1]["type"] == "final"
    pending = json.loads(_get(server + "/api/approvals"))
    assert len(pending) == 1
    done = json.loads(_post(f"{server}/api/approvals/{pending[0]['approval_id']}", {"decision": "approve"}))
    assert done["amount"] == 149.0 and json.loads(_get(server + "/api/approvals")) == []


def test_web_ui_streams_events(server):
    body = _post(server + "/api/chat?stream=1", {"message": "Where is my order NW-1003?"})
    events = [json.loads(line[6:]) for line in body.split("\n\n") if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "user_message" and "tool_call" in types and types[-1] == "done"
    assert "sofia.garcia@example.com" not in body


def test_web_ui_rejects_bad_input(server):
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/chat", {"message": ""})
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/api/traces/nope")
    assert e.value.code == 404
