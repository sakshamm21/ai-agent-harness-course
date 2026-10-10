"""Command line: python3 -m supportbot <command>

  ingest            build the vector index, save it to runs/index.json, print stats
  ask "question"    one message, one reply (add --trace to print the events)
  chat              talk to it in the terminal
  eval              run the 40-conversation eval set
  serve [--port N]  web UI and trace viewer on http://127.0.0.1:8000

No ANTHROPIC_API_KEY: everything runs on the offline MockModel.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from .config import HELP_DIR, RUNS_DIR, SEED_ORDERS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="supportbot", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--trace", action="store_true")
    sub.add_parser("chat")
    sub.add_parser("eval")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)

    if args.cmd == "serve":
        from .server import serve
        serve(args.host, args.port)
        return 0

    if args.cmd == "eval":
        from .evals import format_report, load_evals, run_suite
        report = run_suite(load_evals())
        print(format_report(report))
        return 0 if report["passed"] == report["total"] else 1

    from .ingest import build_index
    index = build_index(HELP_DIR)
    if args.cmd == "ingest":
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        index.save(RUNS_DIR / "index.json")
        articles = {c["article_id"] for c in index.chunks}
        print(f"{len(articles)} articles -> {len(index)} chunks -> {RUNS_DIR / 'index.json'}")
        return 0

    from .agent import SupportAgent, history_append
    from .tools import OrderStore
    from .tracing import Tracer
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    store = OrderStore(RUNS_DIR / "store.db", seed=SEED_ORDERS)
    agent = SupportAgent(index, store, on_event=Tracer())
    conv = uuid.uuid4().hex[:12]
    if args.cmd == "ask":
        reply = agent.handle(args.question, conversation_id=conv)
        print(reply.text)
        if args.trace:
            for e in reply.events:
                print(json.dumps(e))
        print(f"\n(route {reply.route}, trace runs/traces/{conv}.jsonl)", file=sys.stderr)
        return 0

    history: list[dict] = []
    print(f"supportbot (model: {agent.model.name}). Ctrl-D to quit.")
    while True:
        try:
            message = input("you> ").strip()
        except EOFError:
            print()
            return 0
        if message:
            reply = agent.handle(message, history, conversation_id=conv)
            history = history_append(history, message, reply)
            print(f"bot> {reply.text}\n")


if __name__ == "__main__":
    raise SystemExit(main())
