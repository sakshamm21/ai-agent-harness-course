"""Part 9: subagents. The `task` tool runs a child loop with a fresh context and returns a summary."""
import json

from nanoharness.loop import Agent
from nanoharness.model import MockModel, call, say
from nanoharness.permissions import Permissions
from nanoharness.subagent import SUBAGENT_PROMPT, make_task_tool
from nanoharness.tools import ToolRegistry, file_tools


def setup(tmp_path, child_script, parent_script, **kw):
    (tmp_path / "big.py").write_text("SECRET_DETAIL = 1\n" + "# filler\n" * 2000)
    child = MockModel(child_script)
    parent_model = MockModel(parent_script)
    agent = Agent(parent_model, ToolRegistry(file_tools(str(tmp_path))), system="PARENT RULES",
                  subagent_model=child, **kw)
    agent.tools.add(make_task_tool(agent))
    return agent, parent_model, child


def test_task_runs_a_child_with_fresh_context_and_returns_only_its_report(tmp_path):
    agent, parent, child = setup(
        tmp_path,
        [call("read_file", path="big.py"), say("SECRET_DETAIL is defined on line 1 of big.py.")],
        [call("task", description="find SECRET_DETAIL", prompt="Where is SECRET_DETAIL defined?"),
         say("It is in big.py, line 1.")])
    result = agent.run("Find SECRET_DETAIL")
    assert result.final_text == "It is in big.py, line 1."
    report = result.messages[2]["content"][0]["content"]
    assert report.startswith("[subagent: find SECRET_DETAIL; 2 turns]")
    assert "line 1 of big.py" in report
    # fresh context: the child saw only its own prompt, never the parent's conversation
    assert child.seen[0] == [{"role": "user", "content": "Where is SECRET_DETAIL defined?"}]
    assert child.systems[0].startswith(SUBAGENT_PROMPT) and "PARENT RULES" in child.systems[0]
    # the file contents stayed in the child: the parent's context holds the report only
    assert "# filler" not in json.dumps(parent.seen[-1])
    assert "task" in parent.tool_names[0] and "task" not in child.tool_names[0]  # no recursion
    assert agent.child_usage.input_tokens > 0


def test_child_obeys_the_parents_permissions(tmp_path):
    agent, _, child = setup(
        tmp_path,
        [call("write_file", path="evil.txt", content="x"), say("I could not write the file.")],
        [call("task", description="write", prompt="Write evil.txt"), say("done")],
        permissions=Permissions(deny=["write_file"]))
    result = agent.run("go")
    assert not (tmp_path / "evil.txt").exists()
    assert "Permission denied" in json.dumps(child.seen[1])
    assert "could not write" in result.messages[2]["content"][0]["content"]


def test_child_out_of_turns_still_returns_a_note(tmp_path):
    agent, _, _ = setup(tmp_path, [call("list_dir")],
                        [call("task", description="loop", prompt="list forever"), say("ok")],
                        subagent_max_turns=3)
    report = agent.run("go").messages[2]["content"][0]["content"]
    assert report.startswith("[subagent: loop; 3 turns]") and "without a final report" in report
