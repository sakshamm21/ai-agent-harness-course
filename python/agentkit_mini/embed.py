"""A tiny, dependency-free embedding model: hashed word and character-trigram features.

Not a neural model, but it captures word overlap and spelling similarity well enough
to show how semantic-ish search works. A small synonym table makes "refund" find "money back".
"""
from __future__ import annotations

import math
import re
import zlib

DIM = 256

SYNONYMS = {
    "refund": "money_back", "reimburse": "money_back", "money": "money_back", "back": "money_back",
    "cancel": "cancel", "terminate": "cancel", "stop": "cancel", "unsubscribe": "cancel",
    "password": "login", "login": "login", "signin": "login", "sign": "login", "log": "login",
    "ship": "delivery", "shipping": "delivery", "delivery": "delivery", "arrive": "delivery", "package": "delivery",
    "price": "cost", "cost": "cost", "fee": "cost", "charge": "cost", "charged": "cost", "bill": "cost", "billing": "cost",
    "broken": "defect", "damaged": "defect", "defective": "defect", "faulty": "defect",
}

_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "i", "my", "how", "do", "can", "what", "for", "in", "on", "it", "me"}


def _features(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]
    feats = []
    for w in words:
        feats.append("w:" + w)
        if w in SYNONYMS:
            feats += ["s:" + SYNONYMS[w]] * 2
        padded = f"#{w}#"
        feats += ["c:" + padded[i:i + 3] for i in range(len(padded) - 2)]
    return feats


def embed(text: str) -> list[float]:
    """Text -> unit vector of length DIM."""
    v = [0.0] * DIM
    for f in _features(text):
        h = zlib.crc32(f.encode())
        v[h % DIM] += 1.0 if (h >> 16) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorIndex:
    """In-memory vector store: add(text, meta), search(query, k)."""

    def __init__(self):
        self.items: list[tuple[list[float], str, dict]] = []

    def add(self, text: str, meta: dict | None = None) -> None:
        self.items.append((embed(text), text, meta or {}))

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = embed(query)
        scored = sorted(((cosine(q, v), t, m) for v, t, m in self.items), key=lambda x: -x[0])
        return [{"score": round(s, 3), "text": t, **m} for s, t, m in scored[:k]]
