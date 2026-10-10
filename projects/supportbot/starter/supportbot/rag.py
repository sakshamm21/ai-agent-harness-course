"""Part 2: answer questions from the help center, with [article-id] citations.

retrieve -> format documents -> ask the model -> check every citation it made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ingest import VectorIndex
from .model import Model

MIN_SCORE = 0.2   # below this, a chunk is noise (see the score spread in part 1)

RAG_SYSTEM = """You are the support assistant for Northwind Outfitters, an outdoor gear store.
Answer using only the documents provided. After every sentence that uses a document, cite it
with its id in square brackets, like [returns-window]. If the documents do not answer the
question, say you could not find it in the help center. Never invent an article id.
Keep answers to two or three short sentences."""

NOT_FOUND = "I could not find that in our help center. I can pass your question to a person if you like."

CITE_RE = re.compile(r"\[([a-z0-9][a-z0-9-]*)\]")


@dataclass
class RagAnswer:
    text: str
    citations: list[str] = field(default_factory=list)          # ids that were cited and retrieved
    invalid_citations: list[str] = field(default_factory=list)  # ids the model made up
    hits: list[dict] = field(default_factory=list)


def retrieve(index: VectorIndex, question: str, k: int = 3, min_score: float = MIN_SCORE) -> list[dict]:
    """The best chunk from each of the top k articles, dropping anything under min_score.

    Search wider than k (k * 4 chunks), because one article can fill several of the top slots.
    """
    raise NotImplementedError("Part 2: retrieve the best chunks (retrieve)")


def format_documents(hits: list[dict]) -> str:
    """Render hits as <document id="..." title="...">text</document> blocks, one per line."""
    return "\n".join(f'<document id="{h["article_id"]}" title="{h["title"]}">\n{h["text"]}\n</document>'
                     for h in hits)


def build_messages(question: str, hits: list[dict]) -> tuple[str, list[dict]]:
    """System prompt and messages for one RAG call. Documents go before the question."""
    raise NotImplementedError("Part 2: put the documents in the prompt (build_messages)")


def extract_citations(text: str) -> list[str]:
    """Unique [article-id] citations in order of first appearance."""
    raise NotImplementedError("Part 2: find [article-id] citations (extract_citations)")


def check_citations(text: str, hits: list[dict]) -> tuple[str, list[str], list[str]]:
    """Split citations into valid (retrieved) and invalid (made up); strip the invalid ones from text."""
    raise NotImplementedError("Part 2: reject made-up citations (check_citations)")


def answer(question: str, index: VectorIndex, model: Model, k: int = 3) -> RagAnswer:
    """Retrieve, ask, verify. No documents means no model call: say so instead of guessing."""
    raise NotImplementedError("Part 2: retrieve, ask, verify (answer)")
