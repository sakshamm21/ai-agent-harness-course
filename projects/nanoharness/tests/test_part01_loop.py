"""Part 1: the loop. Call the model, run the tools it asks for, append the results, repeat."""
from nanoharness.loop import Agent
from nanoharness.model import MockModel, call, calls, say
from nanoharness.tools import Tool, ToolRegistry


def add(a: int, b: int) -> str:
    return str(a + b)


def boom() -> str:
    raise ValueError("disk on fire")


def registry():
    obj = {"type": "object", "properties": {}}
    return ToolRegistry([Tool("add", "Add two numbers.", obj, add), Tool("boom", "Always fails.", obj, boom),
                         Tool("info", "Returns a dict.", obj, lambda: {"ok": True})])


def test_registry_reports_unknown_tools_and_errors_instead_of_raising():
    reg = registry()
    out, err = reg.call("nope", {})
    assert err and "Unknown tool" in out and "add" in out
    out, err = reg.call("boom", {})
    assert err and out == "ValueError: disk on fire"
    out, err = reg.call("add", {"a": 2, "b": 3})
    assert (out, err) == ("5", False)
    assert reg.call("info", {}) == ('{"ok": true}', False)
    out, err = reg.call("add", {"a": 1})  # missing argument -> TypeError, reported
    assert err and out.startswith("TypeError")


def test_one_tool_call_then_answer():
    model = MockModel([call("add", a=2, b=3), say("2 + 3 = 5")])
    result = Agent(model, registry()).run("What is 2 + 3?")
    assert result.final_text == "2 + 3 = 5"
    assert result.turns == 2 and result.stop_reason == "end_turn"
    roles = [m["role"] for m in result.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    use = result.messages[1]["content"][0]
    res = result.messages[2]["content"][0]
    assert use["type"] == "tool_use" and res["type"] == "tool_result"
    assert res["tool_use_id"] == use["id"] and res["content"] == "5"
    assert result.tool_calls == [{"name": "add", "input": {"a": 2, "b": 3}, "output": "5", "is_error": False}]


def test_parallel_calls_come_back_in_one_user_message():
    model = MockModel([calls(("add", {"a": 1, "b": 1}), ("add", {"a": 2, "b": 2})), say("done")])
    result = Agent(model, registry()).run("two sums")
    results = result.messages[2]["content"]
    assert [b["content"] for b in results] == ["2", "4"]
    ids = [b["id"] for b in result.messages[1]["content"] if b["type"] == "tool_use"]
    assert [b["tool_use_id"] for b in results] == ids


def test_tool_errors_go_back_to_the_model_and_the_loop_continues():
    model = MockModel([call("boom"), say("It failed, sorry.")])
    result = Agent(model, registry()).run("try it")
    block = result.messages[2]["content"][0]
    assert block["is_error"] is True and "disk on fire" in block["content"]
    assert result.final_text == "It failed, sorry."


def test_max_turns_stops_a_model_that_never_finishes():
    model = MockModel([call("add", a=1, b=1)])  # the last response repeats forever
    result = Agent(model, registry(), max_turns=4).run("loop")
    assert result.stop_reason == "max_turns" and result.turns == 4 and result.final_text == ""
    assert model.calls == 4


def test_model_sees_the_growing_transcript_and_usage_adds_up():
    model = MockModel([call("add", a=1, b=2), say("3")])
    events = []
    result = Agent(model, registry(), on_event=events.append).run("sum")
    assert len(model.seen[0]) == 1 and len(model.seen[1]) == 3
    assert model.tool_names[0] == ["add", "boom", "info"]
    assert result.usage.input_tokens > 0 and result.usage.output_tokens > 0
    kinds = [e["type"] for e in events]
    assert kinds == ["model", "tool", "model", "done"]


def test_a_second_run_continues_the_same_conversation():
    model = MockModel([say("hi"), say("still here")])
    agent = Agent(model, registry())
    agent.run("hello")
    agent.run("again")
    assert [m["role"] for m in model.seen[1]] == ["user", "assistant", "user"]
