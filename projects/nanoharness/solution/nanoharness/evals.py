"""Evals: run the harness on small bug-fix tasks and measure pass rate, turns, tokens and cost.

A task is a folder:
    task.json   {"prompt": "...", "check": "python3 -m pytest -q", "oracle": [{"path", "old", "new"}]}
    repo/       the buggy project, including its tests
The agent works on a fresh copy of repo/. The grader then restores the test files from
repo/ (so editing a test never counts as a fix) and runs `check`. Exit code 0 = pass.
"oracle" is the known fix. Only the scripted mock model uses it, so the runner can be
tested offline; a real model never sees it.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass

from .model import cost


@dataclass
class TaskResult:
    task: str
    passed: bool
    turns: int
    input_tokens: int
    output_tokens: int
    cost: float
    stop_reason: str
    check_output: str = ""


def load_tasks(tasks_dir: str, only: list[str] | None = None) -> list[dict]:
    tasks = []
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*", "task.json"))):
        name = os.path.basename(os.path.dirname(path))
        if only and name not in only:
            continue
        with open(path, encoding="utf-8") as f:
            task = json.load(f)
        task.update(name=name, dir=os.path.dirname(path))
        task.setdefault("check", "python3 -m pytest -q -p no:cacheprovider")
        tasks.append(task)
    return tasks


def grade(task: dict, workdir: str, timeout: float = 120) -> tuple[bool, str]:
    """Part 10: Restore every test file (test_*.py, anywhere under the task's repo/) into
    `workdir`, then run task["check"] with the shell in workdir. Return (exit code == 0,
    the last 2000 characters of combined stdout+stderr). A timeout is a fail."""
    repo = os.path.join(task["dir"], "repo")
    for src in glob.glob(os.path.join(repo, "**", "test_*.py"), recursive=True):
        dst = os.path.join(workdir, os.path.relpath(src, repo))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    try:
        p = subprocess.run(task["check"], shell=True, cwd=workdir, capture_output=True, text=True,
                           timeout=timeout, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return False, f"check timed out after {timeout}s"
    return p.returncode == 0, (p.stdout + p.stderr)[-2000:]


def run_task(task: dict, make_agent, price_as: str) -> TaskResult:
    """Part 10: Copy the task's repo/ into a fresh temp dir, build an agent with
    make_agent(task, workdir), run it on task["prompt"], grade the result, delete the temp
    dir and return a TaskResult. Tokens include subagent usage (agent.child_usage); cost is
    model.cost(..., price_as). If the agent raises, the task fails with the error as output."""
    with tempfile.TemporaryDirectory(prefix=f"nh-eval-{task['name']}-") as tmp:
        workdir = os.path.join(tmp, "repo")
        shutil.copytree(os.path.join(task["dir"], "repo"), workdir)
        agent = make_agent(task, workdir)
        try:
            result = agent.run(task["prompt"])
        except Exception as e:  # a crash is a failed task, not a crashed eval run
            return TaskResult(task["name"], False, 0, 0, 0, 0.0, "error", f"{type(e).__name__}: {e}")
        usage = result.usage + agent.child_usage
        passed, out = grade(task, workdir)
        return TaskResult(task["name"], passed, result.turns, usage.input_tokens, usage.output_tokens,
                          cost(usage.input_tokens, usage.output_tokens, price_as), result.stop_reason, out)


def summarize(results: list[TaskResult]) -> dict:
    """Part 10: Aggregate results into {"tasks", "passed", "pass_rate", "avg_turns",
    "input_tokens", "output_tokens", "cost", "cost_per_pass"}. Rates and averages are
    rounded to 3 decimals, cost to 4. pass_rate and avg_turns are 0 for no results;
    cost_per_pass is None when nothing passed."""
    n = len(results)
    passed = sum(r.passed for r in results)
    total_cost = sum(r.cost for r in results)
    return {
        "tasks": n,
        "passed": passed,
        "pass_rate": round(passed / n, 3) if n else 0,
        "avg_turns": round(sum(r.turns for r in results) / n, 3) if n else 0,
        "input_tokens": sum(r.input_tokens for r in results),
        "output_tokens": sum(r.output_tokens for r in results),
        "cost": round(total_cost, 4),
        "cost_per_pass": round(total_cost / passed, 4) if passed else None,
    }


def report(results: list[TaskResult], summary: dict, price_as: str) -> str:
    rows = [f"{'task':<24} {'result':<6} {'turns':>5} {'tokens':>8} {'cost $':>8}"]
    for r in results:
        rows.append(f"{r.task:<24} {'PASS' if r.passed else 'FAIL':<6} {r.turns:>5} "
                    f"{r.input_tokens + r.output_tokens:>8} {r.cost:>8.4f}")
    s = summary
    rows.append(f"\nPassed {s['passed']}/{s['tasks']} ({s['pass_rate']:.0%}), avg {s['avg_turns']} turns, "
                f"{s['input_tokens'] + s['output_tokens']} tokens, ${s['cost']:.4f} (priced as {price_as})")
    return "\n".join(rows)


def to_json(results: list[TaskResult], summary: dict) -> str:
    return json.dumps({"summary": summary, "results": [asdict(r) for r in results]}, indent=2)
