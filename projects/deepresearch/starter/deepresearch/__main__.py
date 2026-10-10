"""python -m deepresearch "your question"   |   python -m deepresearch --eval"""
from __future__ import annotations

import argparse
import json
import sys

from .model import get_models, use_mock


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="deepresearch", description="Multi-agent research over the bundled corpus.")
    p.add_argument("question", nargs="?", help="the research question")
    p.add_argument("--eval", action="store_true", help="run the 10-question eval set and print a scorecard")
    p.add_argument("--no-verify", action="store_true", help="skip the citation verifier (to see what it buys you)")
    p.add_argument("--max-usd", type=float, default=0.50, help="shared cost cap in dollars (default 0.50)")
    p.add_argument("--max-tokens", type=int, default=None, help="shared token cap (default none)")
    p.add_argument("--workers", type=int, default=4, help="parallel workers (default 4)")
    p.add_argument("--trace", action="store_true", help="print orchestrator events to stderr")
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    a = p.parse_args(argv)

    mode = "mock model (offline)" if use_mock() else "real model (ANTHROPIC_API_KEY)"
    print(f"deepresearch: {mode}", file=sys.stderr)
    models = get_models()
    kw = dict(max_usd=a.max_usd, max_tokens=a.max_tokens, max_workers=a.workers)

    if a.eval:
        from .evals import format_scorecard, run_evals
        card = run_evals(models, verify=not a.no_verify, **kw)
        print(format_scorecard(card, "deepresearch evals" + (" (no verifier)" if a.no_verify else "")))
        return 0
    if not a.question:
        p.error("give a question, or --eval")

    from .research import research
    trace = (lambda e: print("  " + json.dumps(e), file=sys.stderr)) if a.trace else None
    res = research(a.question, models=models, verify=not a.no_verify, on_event=trace, **kw)
    if a.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print(res.report)
        status = ", ".join(f"{r.status}" for r in res.results)
        print(f"--- {len(res.sub_questions)} sub-questions [{status}], {res.tokens:,} tokens, "
              f"${res.cost_usd:.4f}{', PARTIAL' if res.partial else ''}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
