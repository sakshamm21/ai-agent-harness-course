#!/usr/bin/env python3
"""Run nanoharness on the bug-fix tasks in evals/tasks/ and report pass rate, turns, tokens, cost.

    python3 evals/run_evals.py --mock                  # scripted oracle model, offline, 15/15
    python3 evals/run_evals.py --min-pass 10           # real model (ANTHROPIC_API_KEY); pass bar 10/15
    python3 evals/run_evals.py --tasks clamp,median --json results.json

Which nanoharness? IMPL=starter or IMPL=solution picks that folder; otherwise an installed
nanoharness, else solution/.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
if os.environ.get("IMPL"):
    sys.path.insert(0, os.path.join(PROJECT, os.environ["IMPL"]))
else:
    try:
        import nanoharness  # noqa: F401
    except ImportError:
        sys.path.insert(0, os.path.join(PROJECT, "solution"))

from nanoharness.cli import build_agent  # noqa: E402
from nanoharness.evals import load_tasks, report, run_task, summarize, to_json  # noqa: E402
from nanoharness.model import DEFAULT_MODEL, AnthropicModel, fixer_mock  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mock", action="store_true", help="scripted oracle model (offline)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tasks", default="", help="comma-separated task names (default: all)")
    ap.add_argument("--tasks-dir", default=os.path.join(HERE, "tasks"))
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--docker", default=None, metavar="IMAGE", help="run the agent's bash in Docker")
    ap.add_argument("--json", default=None, metavar="PATH", help="also write results as JSON")
    ap.add_argument("--min-pass", type=int, default=0, help="exit 1 if fewer tasks pass")
    args = ap.parse_args(argv)

    if not args.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print("No ANTHROPIC_API_KEY set. Use --mock to run offline.", file=sys.stderr)
        return 2
    tasks = load_tasks(args.tasks_dir, [t for t in args.tasks.split(",") if t] or None)

    def make_agent(task: dict, workdir: str):
        model = fixer_mock(task["oracle"], task["check"]) if args.mock else AnthropicModel(args.model)
        # Evals run unattended in a throwaway copy, so "ask" rules auto-approve; deny rules still apply.
        return build_agent(workdir, model, yes=True, docker=args.docker, max_turns=args.max_turns)

    results = []
    for task in tasks:
        r = run_task(task, make_agent, args.model)
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.task}  ({r.turns} turns)", file=sys.stderr, flush=True)
        results.append(r)
    summary = summarize(results)
    print(report(results, summary, args.model))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(to_json(results, summary))
    return 0 if summary["passed"] >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
