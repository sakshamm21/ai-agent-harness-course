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
    """The worker's two tools, bound to one corpus."""

    @tool
    def search(query: str, k: int = 5) -> list:
        """Search the document collection. Returns up to k hits with id, title, url and a snippet.
        Use short keyword queries, like "velmora tunnel length"."""
        return corpus.search(query, k=max(1, min(int(k), 10)))

    @tool
    def fetch_page(doc_id: str) -> dict:
        """Fetch the full text of one document by its id (like "vt-01") or its corpus:// url."""
        d = corpus.fetch(doc_id)
        return {"id": d.id, "title": d.title, "source": d.source, "date": d.date, "url": d.url, "text": d.text}

    return [search, fetch_page]


def parse_claims(text: str, read_ids: list[str]) -> list[Claim]:
    """Parse {"claims": [...]} from the worker's reply.

    Drops sources the worker never fetched, then drops claims left with no source.
    """
    data = extract_json(text)
    if isinstance(data, list):
        data = {"claims": data}
    if not isinstance(data, dict):
        return []
    read = set(read_ids)
    out: list[Claim] = []
    for c in data.get("claims", []):
        if not isinstance(c, dict) or not str(c.get("text", "")).strip():
            continue
        srcs = c.get("sources", [])
        srcs = [srcs] if isinstance(srcs, str) else srcs
        kept = list(dict.fromkeys(s for s in srcs if s in read))
        if kept:
            out.append(Claim(str(c["text"]).strip(), kept))
    return out


def run_worker(sub_question: str, model: Model, corpus: Corpus, max_turns: int = 6) -> WorkerResult:
    """Research one sub-question. Status is "ok" with claims, or "empty" with none.

    Model errors (including BudgetExceeded) are not caught here: the caller decides.
    """
    run = run_loop(model, make_tools(corpus), worker_prompt(sub_question), system=WORKER_SYSTEM,
                   max_turns=max_turns)
    read_ids = list(dict.fromkeys(c["output"]["id"] for c in run.tool_calls
                                  if c["name"] == "fetch_page" and not c["error"]))
    claims = parse_claims(run.final_text, read_ids)
    return WorkerResult(sub_question, "ok" if claims else "empty", claims, read_ids,
                        run.usage.input_tokens, run.usage.output_tokens,
                        "" if claims else f"no cited claims (stop: {run.stop_reason})")
