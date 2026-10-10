"""Part 10: evals. 15 bug-fix tasks; report pass rate, turns, tokens and cost. Plus the whole CLI."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from nanoharness.cli import build_agent
from nanoharness.evals import TaskResult, grade, load_tasks, run_task, summarize
from nanoharness.model import fixer_mock

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_DIR = os.path.join(PROJECT, "evals", "tasks")
TASKS = load_tasks(TASKS_DIR)
IMPL_DIR = os.path.join(PROJECT, os.environ.get("IMPL", "starter"))


def apply(fixes, workdir):
    for fx in fixes:
        p = os.path.join(workdir, fx["path"])
        text = open(p).read()
        assert text.count(fx["old"]) == 1, fx
        open(p, "w").write(text.replace(fx["old"], fx["new"]))


def test_there_are_fifteen_tasks():
    assert len(TASKS) == 15
    for t in TASKS:
        assert t["prompt"] and t["oracle"] and os.path.isdir(os.path.join(t["dir"], "repo"))


@pytest.mark.parametrize("task", TASKS, ids=[t["name"] for t in TASKS])
def test_each_task_is_a_real_bug_and_the_oracle_fixes_it(task, tmp_path):
    wd = str(tmp_path / "repo")
    shutil.copytree(os.path.join(task["dir"], "repo"), wd)
    passed, out = grade(task, wd)
    assert not passed, f"{task['name']} passes before any fix:\n{out}"
    apply(task["oracle"], wd)
    passed, out = grade(task, wd)
    assert passed, out


def test_grade_restores_tests_so_editing_them_does_not_count(tmp_path):
    task = next(t for t in TASKS if t["name"] == "clamp")
    wd = str(tmp_path / "repo")
    shutil.copytree(os.path.join(task["dir"], "repo"), wd)
    with open(os.path.join(wd, "test_bounds.py"), "w") as f:
        f.write("def test_nothing():\n    pass\n")
    assert grade(task, wd)[0] is False


def test_run_task_with_the_oracle_mock():
    task = next(t for t in TASKS if t["name"] == "money_package")
    make = lambda t, wd: build_agent(wd, fixer_mock(t["oracle"], t["check"]), yes=True)
    r = run_task(task, make, "claude-sonnet-5-5")
    assert r.passed and r.turns == 5 and r.stop_reason == "end_turn"
    assert r.input_tokens > 0 and r.output_tokens > 0 and r.cost > 0
    lazy = run_task(task, lambda t, wd: build_agent(wd, fixer_mock([], t["check"]), yes=True), "claude-sonnet-5-5")
    assert not lazy.passed and "failed" in lazy.check_output


def test_run_task_survives_a_crashing_agent():
    class Crash:
        child_usage = None

        def run(self, prompt):
            raise RuntimeError("API down")
    r = run_task(TASKS[0], lambda t, wd: Crash(), "claude-sonnet-5-5")
    assert not r.passed and r.stop_reason == "error" and "API down" in r.check_output


def test_summarize():
    rs = [TaskResult("a", True, 4, 1000, 100, 0.003, "end_turn"),
          TaskResult("b", False, 10, 3000, 300, 0.009, "max_turns"),
          TaskResult("c", True, 7, 2000, 200, 0.006, "end_turn")]
    assert summarize(rs) == {"tasks": 3, "passed": 2, "pass_rate": 0.667, "avg_turns": 7.0,
                             "input_tokens": 6000, "output_tokens": 600, "cost": 0.018, "cost_per_pass": 0.009}
    assert summarize([])["pass_rate"] == 0 and summarize(rs[1:2])["cost_per_pass"] is None


def run(args, cwd, stdin=""):
    env = {**os.environ, "PYTHONPATH": IMPL_DIR, "IMPL": os.environ.get("IMPL", "starter")}
    env.pop("ANTHROPIC_API_KEY", None)
    return subprocess.run([sys.executable, *args], cwd=cwd, env=env, input=stdin, capture_output=True,
                          text=True, timeout=300)


def test_eval_runner_end_to_end_with_the_mock(tmp_path):
    out_json = str(tmp_path / "results.json")
    p = run([os.path.join(PROJECT, "evals", "run_evals.py"), "--mock", "--tasks", "clamp,median,percent",
             "--json", out_json, "--min-pass", "3"], str(tmp_path))
    assert p.returncode == 0, p.stderr
    assert "Passed 3/3 (100%)" in p.stdout
    data = json.load(open(out_json))
    assert data["summary"]["passed"] == 3 and len(data["results"]) == 3


def test_cli_fixes_the_demo_bug_end_to_end(tmp_path):
    demo = str(tmp_path / "demo")
    assert run(["-m", "nanoharness", "--init-demo", demo], str(tmp_path)).returncode == 0
    # without --yes, the harness asks before the edit and the test run: answer y twice
    p = run(["-m", "nanoharness", "--mock", "fix the bug in calc.py"], demo, stdin="y\ny\n")
    assert p.returncode == 0, p.stderr
    assert "Allow edit_file: calc.py? [y/N/a]" in p.stdout + p.stderr
    assert "Fixed the bug in calc.py" in p.stdout and "1 passed" in p.stdout
    assert "len(numbers) + 1" not in open(os.path.join(demo, "calc.py")).read()
    # the session was saved, and --resume continues it
    p = run(["-m", "nanoharness", "--mock", "--yes", "--resume", "run the tests again"], demo)
    assert p.returncode == 0 and "[resumed" in p.stderr
    sessions = os.listdir(os.path.join(demo, ".nanoharness", "sessions"))
    assert len(sessions) == 1


def test_cli_denies_when_nobody_answers(tmp_path):
    demo = str(tmp_path / "demo")
    run(["-m", "nanoharness", "--init-demo", demo], str(tmp_path))
    p = run(["-m", "nanoharness", "--mock", "fix the bug in calc.py"], demo, stdin="")
    assert p.returncode == 0
    assert "len(numbers) + 1" in open(os.path.join(demo, "calc.py")).read()  # nothing was changed
