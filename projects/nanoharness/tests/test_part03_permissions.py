"""Part 3: permissions. deny > ask > allow; ask before writes and commands by default."""
import pytest

from nanoharness.loop import Agent
from nanoharness.model import MockModel, call, say
from nanoharness.permissions import Permissions, Rule, parse_rule
from nanoharness.tools import ToolRegistry, file_tools


def answers(*replies):
    asked = []
    replies = list(replies)

    def prompt(question):
        asked.append(question)
        return replies.pop(0) if replies else ""
    return prompt, asked


def test_parse_rule():
    assert parse_rule("read_file") == Rule("read_file", None)
    assert parse_rule("bash(git *)") == Rule("bash", "git *")
    assert parse_rule("*") == Rule("*", None)
    with pytest.raises(ValueError):
        parse_rule("bash(git")


def test_rule_matching():
    assert Rule("bash", "pytest*").matches("bash", "pytest -q")
    assert not Rule("bash", "pytest*").matches("bash", "rm -rf build")
    assert not Rule("bash", "pytest*").matches("write_file", "pytest.ini")
    assert Rule("*_file", None).matches("edit_file", "a.py")
    assert Rule("edit_file", "src/*").matches("edit_file", "src/a.py")


def test_defaults_read_only_allowed_writes_and_bash_ask():
    p = Permissions()
    assert p.check("read_file", {"path": "a.py"})[0] == "allow"
    assert p.check("grep", {"pattern": "x"})[0] == "allow"
    assert p.check("write_file", {"path": "a.py", "content": ""})[0] == "ask"
    assert p.check("edit_file", {"path": "a.py"})[0] == "ask"
    assert p.check("bash", {"command": "ls"})[0] == "ask"
    assert p.check("bash", {"command": "sudo rm -rf /"})[0] == "deny"
    assert p.check("bash", {"command": "git push origin main"})[0] == "deny"


def test_precedence_deny_then_ask_then_allow():
    p = Permissions(allow=["bash"], ask=["bash(git *)"], deny=["bash(git push*)"])
    assert p.check("bash", {"command": "ls"}) == ("allow", "allowed by rule bash")
    assert p.check("bash", {"command": "git status"})[0] == "ask"
    decision, reason = p.check("bash", {"command": "git push"})
    assert decision == "deny" and "git push*" in reason
    assert Permissions(yes=True).check("bash", {"command": "ls"})[0] == "allow"
    assert Permissions(deny=["bash(rm*)"], yes=True).check("bash", {"command": "rm x"})[0] == "deny"


def test_decide_prompts_y_n_and_always():
    prompt, asked = answers("y", "", "a")
    p = Permissions(prompt=prompt)
    assert p.decide("bash", {"command": "make"}) == (True, "user approved")
    assert asked[0] == "Allow bash: make? [y/N/a] "
    assert p.decide("bash", {"command": "make"}) == (False, "user declined")
    assert p.decide("bash", {"command": "make test"})[0] is True   # "a": always
    assert p.decide("bash", {"command": "make test"})[0] is True   # not asked again
    assert len(asked) == 3
    assert p.decide("bash", {"command": "make testing"})[0] is False  # exact subject only
    assert p.decide("read_file", {"path": "x"})[0] is True and len(asked) == 4
    assert [o for _, _, o in p.log] == ["allow", "deny", "allow", "allow", "deny", "allow"]


def test_agent_does_not_run_a_denied_call(tmp_path):
    prompt, asked = answers("n")
    model = MockModel([call("write_file", path="x.txt", content="hi"), say("ok")])
    agent = Agent(model, ToolRegistry(file_tools(str(tmp_path))), permissions=Permissions(prompt=prompt))
    result = agent.run("write x.txt")
    assert not (tmp_path / "x.txt").exists()
    block = result.messages[2]["content"][0]
    assert block["is_error"] and block["content"].startswith("Permission denied")
    assert asked == ["Allow write_file: x.txt? [y/N/a] "]
