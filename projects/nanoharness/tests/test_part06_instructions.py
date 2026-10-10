"""Part 6: project instructions. AGENTS.md from the working dir goes into the system prompt."""
from nanoharness.instructions import BASE_PROMPT, MAX_INSTRUCTIONS, build_system_prompt, load_instructions
from nanoharness.loop import Agent
from nanoharness.model import MockModel, say
from nanoharness.tools import ToolRegistry


def test_load_agents_md(tmp_path):
    assert load_instructions(str(tmp_path)) is None
    (tmp_path / "CLAUDE.md").write_text("use tabs")
    assert load_instructions(str(tmp_path)) == "use tabs"
    (tmp_path / "AGENTS.md").write_text("Run tests with make test.")
    assert load_instructions(str(tmp_path)) == "Run tests with make test."   # AGENTS.md wins


def test_long_instructions_are_truncated(tmp_path):
    (tmp_path / "AGENTS.md").write_text("x" * (MAX_INSTRUCTIONS + 500))
    text = load_instructions(str(tmp_path))
    assert text.startswith("x" * MAX_INSTRUCTIONS) and text.endswith("[... instructions truncated ...]")
    assert len(text) < MAX_INSTRUCTIONS + 100


def test_system_prompt_layout(tmp_path):
    wd = str(tmp_path)
    plain = build_system_prompt(wd)
    assert plain.startswith(BASE_PROMPT)
    assert f"<env>\nWorking directory: {wd}\n" in plain
    assert "project_instructions" not in plain
    full = build_system_prompt(wd, "Always run make lint.", extra="Be brief.")
    assert '<project_instructions source="AGENTS.md">\nAlways run make lint.\n</project_instructions>' in full
    assert full.index("<env>") < full.index("<project_instructions") < full.index("Be brief.")
    assert full.endswith("Be brief.")


def test_the_model_sees_the_project_instructions(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Never edit generated/ files.")
    system = build_system_prompt(str(tmp_path), load_instructions(str(tmp_path)))
    model = MockModel([say("ok")])
    Agent(model, ToolRegistry(), system=system).run("hi")
    assert "Never edit generated/ files." in model.systems[0]
