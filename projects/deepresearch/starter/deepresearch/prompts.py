"""Every prompt in one place. The mock model reads these exact formats, so keep them stable.

Each system prompt starts with "Role: <name>." That line is harmless for a real model
and lets the offline mock know which agent it is playing.
"""
from __future__ import annotations

import json

PLANNER_SYSTEM = """Role: planner.
You are the lead researcher. Break the user's question into 2 to 4 focused sub-questions that
together answer it. Each sub-question must stand alone: repeat the names it needs, never "it".
Reply with only a JSON array of strings."""

REPLANNER_SYSTEM = """Role: replanner.
You are the lead researcher. Some sub-questions came back with no usable sources.
Write replacement sub-questions for the failed ones only: shorter, plainer wording that a
keyword search can match. Do not repeat a failed sub-question word for word.
Reply with only a JSON array of strings."""

WORKER_SYSTEM = """Role: worker.
You research one sub-question using a small document collection.
1. Call search with a short keyword query.
2. Call fetch_page on the 1 to 3 most relevant results (you may call it several times in one turn).
3. Reply with only JSON: {"claims": [{"text": "...", "sources": ["doc-id"]}]}
Each claim is one factual sentence taken from a page you fetched. Cite the doc id of the page
that states it. If nothing relevant turns up, reply {"claims": []}."""

VERIFIER_SYSTEM = """Role: verifier.
You check one citation. Decide whether the source text, on its own, states the claim.
Paraphrase is fine; a claim that adds numbers, names or causes the source does not give is not.
Reply with only JSON: {"supported": true or false, "reason": "one short sentence"}."""

REVISER_SYSTEM = """Role: reviser.
A verifier rejected some of your citations. For each rejected claim, cite a page you read that
does state it, or drop the claim. Keep claims that were not rejected exactly as they are.
Reply with only JSON: {"claims": [{"text": "...", "sources": ["doc-id"]}]}"""

WRITER_SYSTEM = """Role: writer.
Write a short research report in Markdown from the findings you are given, and nothing else.
Start with "# " and the question. Add one "## " section per sub-question with the claims as bullets.
After every bullet, cite its sources by doc id in square brackets, like [vt-03] or [vt-03, vt-04].
Use only the claims and doc ids in the findings. If there are gaps, list them under "## Gaps"."""


def plan_prompt(question: str, max_subquestions: int) -> str:
    return f"Question: {question}\nWrite at most {max_subquestions} sub-questions."


def replan_prompt(question: str, failed: list[str], answered: list[str], max_subquestions: int) -> str:
    lines = [f"Question: {question}", "", "Answered:"]
    lines += [f"- {q}" for q in answered] or ["- (none)"]
    lines += ["", "Failed:"]
    lines += [f"- {q}" for q in failed]
    lines += ["", f"Write at most {max_subquestions} replacement sub-questions."]
    return "\n".join(lines)


def worker_prompt(sub_question: str) -> str:
    return f"Sub-question: {sub_question}"


def verify_prompt(claim: str, doc: dict) -> str:
    return (f"Claim: {claim}\n\nSource {doc['id']} ({doc['title']}):\n{doc['text']}\n\n"
            'Reply with JSON {"supported": true or false, "reason": "..."}.')


def revise_prompt(sub_question: str, claims: list[dict], failures: list[dict], pages: list[dict]) -> str:
    parts = [f"Sub-question: {sub_question}", "",
             "Draft claims (JSON):", json.dumps({"claims": claims}), "",
             "Verifier feedback (JSON):", json.dumps(failures), "", "Pages you read:"]
    for p in pages:
        parts += [f"=== {p['id']}", p["text"]]
    parts += ["=== end", "", "Return the revised claims as JSON."]
    return "\n".join(parts)


def writer_prompt(handoff: dict) -> str:
    return "Write the report.\n\nFindings (JSON):\n" + json.dumps(handoff, indent=1)
