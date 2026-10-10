"""Part 5: the report writer. A structured handoff in, Markdown with numbered sources out.

The writer gets a clean JSON handoff (verified claims grouped by sub-question, plus gaps),
never the workers' transcripts. It cites by doc id. Code, not the model, then turns ids
into numbers [1], [2] and appends the Sources list, so a number can never point at a
document nobody read.
"""
from __future__ import annotations

import re

from .corpus import Corpus
from .model import Model
from .prompts import WRITER_SYSTEM, writer_prompt
from .records import WorkerResult

# [vt-03] or [vt-03, kw-01]
CITE = re.compile(r"\[((?:[a-z]{2,4}-\d{2,3})(?:\s*,\s*[a-z]{2,4}-\d{2,3})*)\]")


def build_handoff(question: str, results: list[WorkerResult], corpus: Corpus) -> dict:
    """The writer's whole input: question, sections of verified claims, gaps, and source titles."""
    sections, gaps, used = [], [], []
    for r in results:
        if r.ok and r.claims:
            sections.append({"sub_question": r.sub_question, "claims": [c.to_dict() for c in r.claims]})
            used += [s for c in r.claims for s in c.sources]
        else:
            gaps.append(r.sub_question)
    sources = {i: corpus.fetch(i).title for i in dict.fromkeys(used) if i in corpus.docs}
    return {"question": question, "sections": sections, "gaps": gaps, "sources": sources}


def number_citations(markdown: str, corpus: Corpus, allowed: set[str]) -> str:
    """Replace [doc-id] cites with [n] in order of first use and append a numbered Sources list.

    Ids outside `allowed` (not in the handoff) are removed; a cite left empty disappears.
    """
    numbers: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        ids = [i.strip() for i in m.group(1).split(",")]
        nums = []
        for i in ids:
            if i in allowed and i in corpus.docs:
                numbers.setdefault(i, len(numbers) + 1)
                nums.append(numbers[i])
        return "[" + ", ".join(str(n) for n in sorted(set(nums))) + "]" if nums else ""

    body = CITE.sub(sub, markdown)
    body = re.sub(r"[ \t]+([.,;:])", r"\1", body).rstrip()
    lines = ["", "", "## Sources", ""]
    for i, n in sorted(numbers.items(), key=lambda x: x[1]):
        d = corpus.fetch(i)
        lines.append(f"{n}. {d.title}. {d.source}, {d.date}. <{d.url}> ({d.id})")
    return body + ("\n".join(lines) if numbers else "") + "\n"


def write_report(question: str, results: list[WorkerResult], model: Model, corpus: Corpus,
                 partial: bool = False) -> str:
    """Hand off, let the writer draft, then number the citations."""
    handoff = build_handoff(question, results, corpus)
    if not handoff["sections"]:
        md = f"# {question}\n\nNo sub-question produced verified findings, so there is nothing to report.\n"
        if handoff["gaps"]:
            md += "\n## Gaps\n\n" + "\n".join(f"- Not answered: {g}" for g in handoff["gaps"]) + "\n"
    else:
        md = model.complete([{"role": "user", "content": writer_prompt(handoff)}], system=WRITER_SYSTEM,
                            max_tokens=3000).text
    if partial:
        note = "> Partial report: the cost cap stopped research before every sub-question was answered."
        head, sep, rest = md.partition("\n")
        md = f"{head}\n\n{note}\n{rest}" if head.startswith("# ") else f"{note}\n\n{md}"
    return number_citations(md, corpus, set(handoff["sources"]))


def parse_report(markdown: str) -> tuple[list[tuple[str, list[str]]], dict[int, str]]:
    """Read a finished report back: ([(sentence, [doc ids])], {number: doc id}). Used by the evals."""
    body, _, src = markdown.partition("\n## Sources")
    num_to_id = {int(n): i for n, i in re.findall(r"^(\d+)\. .*\(([a-z]{2,4}-\d{2,3})\)\s*$", src, re.M)}
    cited = []
    for line in body.splitlines():
        for m in re.finditer(r"([^\[\]]+?)\s*\[(\d+(?:\s*,\s*\d+)*)\]", line.lstrip("-* ")):
            ids = [num_to_id[int(n)] for n in m.group(2).split(",") if int(n) in num_to_id]
            cited.append((m.group(1).strip(" .;"), ids))
    return cited, num_to_id
