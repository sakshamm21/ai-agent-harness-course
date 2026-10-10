"""Part 7: an eval set of 40 conversations, graded two ways.

Exact checks for what must be exact: the route, the tool calls and their arguments, the citations.
An LLM judge for what is fuzzy: does the answer say the right things in words a customer can use?
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .agent import SupportAgent, history_append
from .config import EVALS, HELP_DIR, POISONED_DIR, SEED_ORDERS
from .ingest import VectorIndex, build_index
from .model import JUDGE_MARK, Model, MockModel
from .tools import OrderStore

JUDGE_SYSTEM = f"""{JUDGE_MARK} for an outdoor gear store.
You get the customer's QUESTION, the bot's ANSWER and a RUBRIC. Check each rubric line against the
answer. Paraphrases count; contradictions and missing points do not. Reply with JSON only:
{{"pass": true or false, "score": 0.0 to 1.0, "reason": "one sentence"}}"""


def load_evals(path: str | Path = EVALS) -> list[dict]:
    """One JSON object per line; blank lines and lines starting with # are skipped."""
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            cases.append(json.loads(line))
    return cases


# ---------------------------------------------------------------- exact checks

def _args_match(expected: dict, actual: dict) -> bool:
    for k, v in expected.items():
        a = actual.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            try:
                if abs(float(a) - float(v)) > 0.005:
                    return False
            except (TypeError, ValueError):
                return False
        elif str(a).lower() != str(v).lower():
            return False
    return True


def check_tool_calls(expected: list[dict], actual: list[dict]) -> list[str]:
    """Problems with the executed tool calls (blocked calls do not count). Empty list means exact match.

    expected: [{"name": "lookup_order", "args": {"order_id": "NW-1003"}}]. args is a subset:
    keys you leave out (like reason) are not checked. Order matters.
    """
    raise NotImplementedError("Part 7: exact tool-call checks (check_tool_calls)")


def check_exact(case: dict, run: dict) -> list[str]:
    exp = case["expect"]
    problems = []
    if "route" in exp and run["route"] != exp["route"]:
        problems.append(f"route {run['route']}, expected {exp['route']}")
    problems += check_tool_calls(exp.get("tool_calls", []), run["tool_calls"])
    for c in exp.get("cites", []):
        if c not in run["citations"]:
            problems.append(f"missing citation [{c}]")
    return problems


# ---------------------------------------------------------------- the judge

def build_judge_prompt(question: str, answer: str, rubric: dict) -> tuple[str, list[dict]]:
    lines = [f"- must mention: {m}" for m in rubric.get("must_mention", [])]
    lines += [f"- must not mention: {m}" for m in rubric.get("must_not_mention", [])]
    content = f"QUESTION: {question}\nANSWER: {answer}\nRUBRIC:\n" + ("\n".join(lines) or "- is polite and on topic")
    return JUDGE_SYSTEM, [{"role": "user", "content": content}]


def parse_judgment(text: str) -> dict:
    """Pull the first JSON object out of the judge's reply. Unparseable means fail, not crash."""
    raise NotImplementedError("Part 7: parse the judge's verdict (parse_judgment)")


def judge(question: str, answer: str, rubric: dict, model: Model) -> dict:
    """One judge call (build_judge_prompt, max_tokens=200), parsed with parse_judgment."""
    raise NotImplementedError("Part 7: ask the judge (judge)")


# ---------------------------------------------------------------- running

@dataclass
class CaseResult:
    id: str
    passed: bool
    exact_problems: list[str]
    judgment: dict
    run: dict = field(default_factory=dict)


def run_case(case: dict, index: VectorIndex, model_factory: Callable[[], Model], seed: Path = SEED_ORDERS) -> dict:
    """Play every user turn through a fresh agent and a fresh store. Returns what happened."""
    store = OrderStore(":memory:", seed=seed)
    agent = SupportAgent(index, store, model=model_factory())
    history: list[dict] = []
    calls: list[dict] = []
    reply = None
    for i, turn in enumerate(case["turns"]):
        reply = agent.handle(turn, history, conversation_id=f"eval-{case['id']}")
        calls += reply.tool_calls
        history = history_append(history, turn, reply)
    return {"route": reply.route, "text": reply.text, "citations": reply.citations, "tool_calls": calls,
            "refunds": store.rows("refunds"), "approvals": store.rows("approvals")}


def run_suite(cases: list[dict], model_factory: Callable[[], Model] = MockModel,
              judge_model: Model | None = None) -> dict:
    """Run every case; a case passes when the exact checks and the judge both pass.

    Build the index once per kind (help center, or help center + POISONED_DIR for cases with
    "poisoned": true). run_case, check_exact, then judge the last turn against case["expect"].
    Returns {"total", "passed", "exact_pass_rate", "judge_pass_rate", "results": [CaseResult]}.
    """
    raise NotImplementedError("Part 7: run the eval set (run_suite)")


def format_report(report: dict) -> str:
    lines = [f"{'case':34} {'exact':6} {'judge':6} notes"]
    for r in report["results"]:
        notes = "; ".join(r.exact_problems + ([] if r.judgment["pass"] else [r.judgment["reason"]]))
        lines.append(f"{r.id:34} {'ok' if not r.exact_problems else 'FAIL':6} "
                     f"{'ok' if r.judgment['pass'] else 'FAIL':6} {notes}")
    lines.append(f"\n{report['passed']}/{report['total']} passed  (exact {report['exact_pass_rate']:.0%}, "
                 f"judge {report['judge_pass_rate']:.0%})")
    return "\n".join(lines)
