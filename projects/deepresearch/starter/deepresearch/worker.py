"""Part 2: a worker agent. One sub-question in, cited claims out.

The worker is an ordinary agent loop with two tools, `search` and `fetch_page`. Its final
reply is JSON claims. We keep only citations to pages it actually fetched: a worker that
cites a page it never opened is guessing.
"""
from __future__ import annotations

from .corpus import Corpus
from .loop import run_loop
from .model import Model
from .prompts import WORKER_SYSTEM, worker_prompt
from .records import Claim, WorkerResult
from .textutil import extract_json
from .tools import Tool, tool


def make_tools(corpus: Corpus) -> list[Tool]:
    """The worker's two tools, bound to one corpus: [search, fetch_page].

    Use the @tool decorator on two inner functions. Their names, type hints and
    docstrings become the schema the model sees:
      search(query: str, k: int = 5) -> list     (corpus.search, k clamped to 1..10)
      fetch_page(doc_id: str) -> dict            ({id, title, source, date, url, text})
    """
    raise NotImplementedError("Part 2: build the search and fetch_page tools (make_tools)")


def parse_claims(text: str, read_ids: list[str]) -> list[Claim]:
    """Parse {"claims": [{"text", "sources"}]} from the worker's reply.

    Accept a bare list too. Skip claims with empty text. Keep only sources in read_ids
    (deduplicated, in order), then drop claims left with no source.
    """
    raise NotImplementedError("Part 2: parse cited claims from the worker's reply (parse_claims)")


def run_worker(sub_question: str, model: Model, corpus: Corpus, max_turns: int = 6) -> WorkerResult:
    """Research one sub-question. Status "ok" with claims, or "empty" with none.

    1. run_loop(model, make_tools(corpus), worker_prompt(sub_question), system=WORKER_SYSTEM, ...).
    2. read_ids = ids of successful fetch_page calls (run.tool_calls), in order, no repeats.
    3. claims = parse_claims(run.final_text, read_ids).
    4. Return a WorkerResult with the claims, read_ids and the run's token usage.
    Do not catch model errors here; run_parallel (part 3) decides what they mean.
    """
    raise NotImplementedError("Part 2: run one worker agent (run_worker)")
