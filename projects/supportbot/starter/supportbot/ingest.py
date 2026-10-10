"""Part 1: ingest the help center into a local vector index.

Pipeline: Markdown files -> articles -> chunks -> vectors -> VectorIndex.
Everything is pure Python: no numpy, no vector database. 60 articles make about
120 chunks, and a linear scan over 120 vectors takes well under a millisecond.
"""
from __future__ import annotations

import json
import math
import re
import zlib
from pathlib import Path

DIM = 512

# A tiny synonym table, so "money back" can find an article that says "refund".
# A neural embedding model learns this from data; we write it by hand.
CONCEPTS = {
    "refund": "money", "reimburse": "money", "money": "money", "credit": "money", "repay": "money",
    "cancel": "cancel", "stop": "cancel", "abort": "cancel",
    "password": "login", "login": "login", "signin": "login", "locked": "login",
    "ship": "shipping", "shipping": "shipping", "deliver": "shipping", "delivery": "shipping",
    "arrive": "shipping", "package": "shipping", "parcel": "shipping", "courier": "shipping",
    "price": "cost", "cost": "cost", "fee": "cost", "charge": "cost", "pay": "cost", "bill": "cost",
    "broken": "defect", "damage": "defect", "defective": "defect", "faulty": "defect", "torn": "defect",
    "size": "fit", "fit": "fit", "sizing": "fit", "small": "fit", "large": "fit", "tight": "fit",
    "return": "return", "send": "return", "exchange": "return",
    "track": "track", "tracking": "track", "where": "track", "status": "track",
    "warranty": "warranty", "guarantee": "warranty", "repair": "warranty",
    "long": "time", "days": "time", "day": "time", "window": "time", "soon": "time", "quickly": "time",
    "wash": "care", "clean": "care", "care": "care", "dry": "care",
    "instalment": "instalment", "installment": "instalment", "split": "instalment",
    "setup": "setup", "set": "setup", "pitch": "setup", "practise": "setup",
}

STOPWORDS = set("""a an the is are was were be been am i me my you your we our us it its this that these those
to of and or in on at for with from by as do does did can could would should will may how what when where
which who why there here have has had not no so if then than too very just about into out up any some all
get please hi hello thanks want need""".split())


def stem(word: str) -> str:
    """Crude suffix stripping: 'returns', 'returned', 'returning' -> 'return'."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


# ---------------------------------------------------------------- articles

def parse_article(path: str | Path) -> dict:
    """Read one Markdown article with a front-matter block.

    Returns {"id", "title", "category", "body", "path"}. body is the Markdown after the
    front matter. Raises ValueError if the front matter has no id.
    """
    raise NotImplementedError("Part 1: parse one article (parse_article)")


def load_articles(*dirs: str | Path) -> list[dict]:
    """Parse every *.md file in the given directories, sorted by file name."""
    out = []
    for d in dirs:
        out += [parse_article(p) for p in sorted(Path(d).glob("*.md"))]
    return out


# ---------------------------------------------------------------- chunking

def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def chunk_article(article: dict, max_words: int = 60, overlap: int = 1) -> list[dict]:
    """Split an article into chunks of at most max_words words (title not counted).

    Pack sentences in order; start a new chunk when the next sentence would not fit.
    Each chunk starts with the article title, so a chunk still makes sense on its own,
    and repeats the last `overlap` sentences of the previous chunk.
    Returns [{"chunk_id": "<id>#<n>", "article_id", "title", "text"}].
    """
    raise NotImplementedError("Part 1: split an article into chunks (chunk_article)")


# ---------------------------------------------------------------- embedding

def features(text: str) -> list[tuple[str, float]]:
    """Weighted features for a text: word stems, concepts, and character trigrams."""
    out: list[tuple[str, float]] = []
    for raw in re.findall(r"[a-z0-9]+", text.lower()):
        if raw in STOPWORDS:
            continue
        w = stem(raw)
        out.append(("w:" + w, 1.0))
        concept = CONCEPTS.get(raw) or CONCEPTS.get(w)
        if concept:
            out.append(("k:" + concept, 1.0))
        padded = f"#{w}#"
        out += [("c:" + padded[i:i + 3], 0.2) for i in range(len(padded) - 2)]
    return out


def embed(text: str) -> list[float]:
    """Text -> unit-length vector of DIM floats (the hashing trick: feature -> bucket).

    For each (feature, weight) in features(text): h = zlib.crc32(feature.encode()); add the
    weight to bucket h % DIM, with sign + if bit 20 of h is set, else -. Then divide by the
    vector's length (an empty text stays all zeros).
    """
    raise NotImplementedError("Part 1: turn text into a vector (embed)")


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two unit vectors is just their dot product."""
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------- the index

class VectorIndex:
    """A list of (vector, chunk) pairs with brute-force cosine search."""

    def __init__(self):
        self.vectors: list[list[float]] = []
        self.chunks: list[dict] = []

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunk: dict) -> None:
        self.vectors.append(embed(chunk["text"]))
        self.chunks.append(chunk)

    def search(self, query: str, k: int = 4) -> list[dict]:
        """Top k chunks by cosine similarity: [{**chunk, "score"}], best first.

        Embed the query once, score every stored vector, sort by score (ties: insertion order),
        round scores to 4 places.
        """
        raise NotImplementedError("Part 1: search the index (search)")

    def save(self, path: str | Path) -> None:
        data = {"dim": DIM, "chunks": self.chunks, "vectors": [[round(x, 6) for x in v] for v in self.vectors]}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "VectorIndex":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("dim") != DIM:
            raise ValueError(f"index was built with dim {data.get('dim')}, this code uses {DIM}: rebuild it")
        idx = cls()
        idx.chunks, idx.vectors = data["chunks"], data["vectors"]
        return idx


def build_index(*dirs: str | Path, max_words: int = 60) -> VectorIndex:
    """Load, chunk and embed every article in dirs."""
    raise NotImplementedError("Part 1: load, chunk and embed the help center (build_index)")
