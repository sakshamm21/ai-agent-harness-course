"""Part 5: context. Count tokens; compact by summarization at 70% of the window."""
import json

from nanoharness.context import ContextManager, count_messages, count_tokens
from nanoharness.loop import Agent
from nanoharness.model import MockModel, call, say
from nanoharness.tools import Tool, ToolRegistry


def test_count_tokens_is_about_four_chars_per_token():
    assert count_tokens("") == 0
    assert count_tokens("abc") == 1
    assert count_tokens("abcd") == 1
    assert count_tokens("abcde") == 2
    assert count_tokens("x" * 4000) == 1000


def test_count_messages_counts_system_tools_and_blocks():
    block = {"type": "tool_result", "tool_use_id": "t1", "content": "y" * 400}
    msgs = [{"role": "user", "content": "x" * 400}, {"role": "user", "content": [block]}]
    tool = {"name": "t", "description": "d", "input_schema": {}}
    expected = 25 + count_tokens(json.dumps(tool)) + (4 + 100) + (4 + count_tokens(json.dumps(block)))
    assert count_messages(msgs, system="s" * 100, tools=[tool]) == expected


def test_should_compact_at_seventy_percent():
    cm = ContextManager(window=1000)
    two = lambda chars: [{"role": "user", "content": "a" * chars}, {"role": "assistant", "content": "ok"}]
    assert not cm.should_compact(two(4 * 680))   # 680 + 4 + 5 = 689 tokens < 700
    assert cm.should_compact(two(4 * 700))       # 709 tokens >= 700
    assert not cm.should_compact([{"role": "user", "content": "a" * 8000}])  # one message: nothing to compact


def test_compact_replaces_the_transcript_with_a_summary():
    summarizer = MockModel([say("User wants X. Edited a.py. Next: run tests.")])
    cm = ContextManager(window=1000, summarizer=summarizer)
    msgs = [{"role": "user", "content": "Fix the bug in a.py"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "read_file",
                                               "input": {"path": "a.py"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "code"}]}]
    out = cm.compact(msgs)
    assert len(out) == 1 and out[0]["role"] == "user"
    assert "User wants X. Edited a.py. Next: run tests." in out[0]["content"]
    assert out[0]["content"].startswith("This session was compacted.")
    assert cm.compactions == 1
    prompt = summarizer.seen[0][0]["content"]
    assert "Fix the bug in a.py" in prompt and "read_file" in prompt   # the transcript went to the summarizer


def test_agent_compacts_a_long_session_and_keeps_going():
    big = Tool("dump", "Returns a lot of text.", {"type": "object", "properties": {}}, lambda: "z" * 3000)
    model = MockModel([call("dump"), call("dump"), call("dump"), call("dump"), say("finished")])
    summarizer = MockModel([say("SUMMARY: dumped several times.")])
    cm = ContextManager(window=2000, summarizer=summarizer)
    events = []
    result = Agent(model, ToolRegistry([big]), context=cm, on_event=events.append).run("dump it all")
    assert result.final_text == "finished"
    assert cm.compactions >= 1 and any(e["type"] == "compact" for e in events)
    after = [seen for seen in model.seen if "SUMMARY" in json.dumps(seen[0])]
    assert after, "the model should continue from the summary"
    assert all(count_messages(s) < 2000 for s in model.seen)
