"""Part 8: sessions. An append-only JSONL transcript, and --resume from it."""
import json

from nanoharness.loop import Agent
from nanoharness.model import MockModel, call, say
from nanoharness.session import Session, find_session, repair_transcript
from nanoharness.tools import Tool, ToolRegistry

ECHO = Tool("echo", "Echo.", {"type": "object", "properties": {}}, lambda text: text)


def lines(path):
    return [json.loads(x) for x in open(path)]


def test_write_appends_one_json_line_per_event(tmp_path):
    s = Session.create(str(tmp_path), model="mock", session_id="s1")
    s.append({"role": "user", "content": "héllo"})
    evs = lines(s.path)
    assert [e["type"] for e in evs] == ["meta", "message"]
    assert evs[0]["id"] == "s1" and evs[1]["message"]["content"] == "héllo"
    assert s.path.endswith(".nanoharness/sessions/s1.jsonl")


def test_load_replays_messages_and_compactions(tmp_path):
    s = Session.create(str(tmp_path), session_id="s2")
    s.append({"role": "user", "content": "one"})
    s.append({"role": "assistant", "content": "two"})
    assert s.load() == [{"role": "user", "content": "one"}, {"role": "assistant", "content": "two"}]
    s.record_compaction([{"role": "user", "content": "summary"}])
    s.append({"role": "assistant", "content": "three"})
    assert s.load() == [{"role": "user", "content": "summary"}, {"role": "assistant", "content": "three"}]
    with open(s.path, "a") as f:
        f.write('{"type": "message", "mess')  # crashed mid-write
    assert len(s.load()) == 2


def test_repair_closes_dangling_tool_calls():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}},
                                              {"type": "tool_use", "id": "t2", "name": "bash", "input": {}}]}]
    fixed = repair_transcript(msgs)
    assert len(fixed) == 3 and len(msgs) == 2  # does not mutate its input
    assert [b["tool_use_id"] for b in fixed[2]["content"]] == ["t1", "t2"]
    assert all(b["is_error"] and "Interrupted" in b["content"] for b in fixed[2]["content"])
    assert repair_transcript(msgs[:1]) == msgs[:1]


def test_agent_saves_everything_and_resumes(tmp_path):
    s = Session.create(str(tmp_path), session_id="run")
    first = Agent(MockModel([call("echo", text="hi"), say("said hi")]), ToolRegistry([ECHO]), session=s)
    first.run("say hi")
    assert Session(s.path).load() == first.messages
    assert find_session(str(tmp_path)).id == "run"
    assert find_session(str(tmp_path), "nope") is None

    resumed = find_session(str(tmp_path))
    model = MockModel([say("you asked me to say hi")])
    second = Agent(model, ToolRegistry([ECHO]), session=resumed, messages=resumed.load())
    second.run("what did I ask?")
    assert model.seen[0][0] == {"role": "user", "content": "say hi"} and len(model.seen[0]) == 5
    assert len(Session(s.path).load()) == 6
