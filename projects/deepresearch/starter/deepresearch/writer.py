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
    """The writer's whole input:
        {"question": ..., "sections": [{"sub_question", "claims": [claim dicts]}],
         "gaps": [sub-questions with no ok claims], "sources": {doc id: title}}
    sources lists every cited id once, in order of first use.
    """
    raise NotImplementedError("Part 5: build the structured handoff (build_handoff)")


def number_citations(markdown: str, corpus: Corpus, allowed: set[str]) -> str:
    """Replace [doc-id] cites with [n] in order of first use and append a numbered Sources list.

    Use the CITE regex. Ids outside `allowed` are removed; a cite left empty disappears
    (tidy the stray space before punctuation). Append "## Sources" with one line per number:
        1. <title>. <source>, <date>. <<url>> (<id>)
    No citations at all: no Sources section.
    """
    raise NotImplementedError("Part 5: number the citations and list sources (number_citations)")


def write_report(question: str, results: list[WorkerResult], model: Model, corpus: Corpus,
                 partial: bool = False) -> str:
    """Hand off, let the writer draft, then number the citations.

    1. handoff = build_handoff(...).
    2. No sections: write a short "# question" report yourself that lists the gaps (no model call).
       Otherwise one call: writer_prompt(handoff) with WRITER_SYSTEM.
    3. partial: put a line containing "Partial report" right under the "# " title.
    4. return number_citations(md, corpus, set(handoff["sources"])).
    """
    raise NotImplementedError("Part 5: write the report (write_report)")


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
