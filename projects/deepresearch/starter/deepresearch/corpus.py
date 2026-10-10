"""Part 2: the offline document collection the workers search.

Each document is a Markdown file in data/corpus/ with a small front matter block:

    ---
    id: vt-01
    title: Velmora Tunnel opens to passenger trains
    source: Northbay Gazette
    date: 2019-06-14
    url: corpus://northbay-gazette/velmora-tunnel-opens
    ---
    Body text...

search() ranks documents with BM25 over title and body words. fetch() returns one
document by id or by its corpus:// URL. Both are deterministic, so tests are stable.
"""
from __future__ import annotations

import math
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .textutil import sentences, tokenize

DATA_DIR = Path(os.environ.get("DEEPRESEARCH_DATA", Path(__file__).resolve().parents[2] / "data"))
CORPUS_DIR = DATA_DIR / "corpus"


@dataclass
class Doc:
    id: str
    title: str
    source: str
    date: str
    url: str
    text: str

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "source": self.source, "date": self.date,
                "url": self.url, "text": self.text}


def parse_doc(raw: str) -> Doc:
    """Split '---' front matter (key: value lines) from the body."""
    if not raw.startswith("---"):
        raise ValueError("document has no front matter")
    _, head, body = raw.split("---", 2)
    meta = {}
    for line in head.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return Doc(meta["id"], meta["title"], meta.get("source", ""), meta.get("date", ""),
               meta.get("url", f"corpus://{meta['id']}"), body.strip())


class Corpus:
    """An in-memory BM25 index over a folder of documents."""

    def __init__(self, docs: list[Doc]):
        self.docs = {d.id: d for d in docs}
        self.by_url = {d.url: d for d in docs}
        # The title counts twice: a word in the headline says more than one in the body.
        self._tf = {d.id: Counter(tokenize(d.title) * 2 + tokenize(d.text)) for d in docs}
        self._len = {i: sum(tf.values()) for i, tf in self._tf.items()}
        self._avg = sum(self._len.values()) / max(1, len(self._len))
        df: Counter = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        n = len(docs)
        self._idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    @classmethod
    def load(cls, folder: str | Path = CORPUS_DIR) -> "Corpus":
        files = sorted(Path(folder).glob("*.md"))
        if not files:
            raise FileNotFoundError(f"no documents in {folder}")
        return cls([parse_doc(f.read_text(encoding="utf-8")) for f in files])

    def __len__(self) -> int:
        return len(self.docs)

    def score(self, query: str, doc_id: str, k1: float = 1.4, b: float = 0.75) -> float:
        tf, dl = self._tf[doc_id], self._len[doc_id]
        s = 0.0
        for w in set(tokenize(query)):
            f = tf.get(w, 0)
            if f:
                s += self._idf[w] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self._avg))
        return s

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Top-k hits as {id, title, url, snippet}. Ties break by id so results never shuffle.

        1. Score every doc id with self.score(query, doc_id).
        2. Keep scores above 0, sort by (-score, id), take the first k.
        3. Return self._hit(doc_id, query) for each.
        """
        raise NotImplementedError("Part 2: rank documents for a query (Corpus.search)")

    def _hit(self, doc_id: str, query: str) -> dict:
        d = self.docs[doc_id]
        q = set(tokenize(query))
        sents = sentences(d.text)
        best = max(sents, key=lambda s: len(q & set(tokenize(s)))) if sents else ""
        return {"id": d.id, "title": d.title, "url": d.url, "snippet": best[:200]}

    def fetch(self, ref: str) -> Doc:
        """A document by id ("vt-01") or URL ("corpus://..."). Raises KeyError if unknown.

        Look in self.docs, then self.by_url. Raise KeyError with a helpful message otherwise:
        the message goes back to the model as a tool error.
        """
        raise NotImplementedError("Part 2: look a document up by id or url (Corpus.fetch)")
