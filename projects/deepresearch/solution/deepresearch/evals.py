"""Part 6: evals. Ten questions with reference facts; score fact recall and citation precision.

Fact recall: the share of reference facts the report states. A fact matches when every one
of its `match` strings appears in the report body (case-insensitive).

Citation precision: the share of (sentence, cited document) pairs where the document really
backs the sentence. The default judge is textutil.supports, a deterministic word-overlap
check; pass judge= to use a model instead.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .corpus import DATA_DIR, Corpus
from .model import Model
from .research import research
from .textutil import supports
from .writer import parse_report

EVALS_PATH = DATA_DIR / "evals.jsonl"


@dataclass
class EvalRow:
    id: str
    question: str
    recall: float
    precision: float
    facts_found: int
    facts_total: int
    citations: int
    cost_usd: float
    tokens: int
    missed: list[str] = field(default_factory=list)


@dataclass
class Scorecard:
    rows: list[EvalRow]

    @property
    def recall(self) -> float:
        total = sum(r.facts_total for r in self.rows)
        return sum(r.facts_found for r in self.rows) / total if total else 0.0

    @property
    def precision(self) -> float:
        total = sum(r.citations for r in self.rows)
        return sum(r.precision * r.citations for r in self.rows) / total if total else 0.0

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.rows)


def load_evals(path: str | Path = EVALS_PATH) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower())


def fact_recall(report: str, facts: list[dict]) -> tuple[float, list[str]]:
    """(recall, facts missed). The Sources list does not count: titles are not answers."""
    body = _norm(report.split("\n## Sources", 1)[0])
    missed = [f["fact"] for f in facts if not all(_norm(m) in body for m in f["match"])]
    return (1 - len(missed) / len(facts) if facts else 0.0), missed


def citation_precision(report: str, corpus: Corpus,
                       judge: Callable[[str, str], bool] = supports) -> tuple[float, int]:
    """(precision, number of citations checked). A report with no citations scores 0."""
    pairs = [(text, i) for text, ids in parse_report(report)[0] for i in ids]
    if not pairs:
        return 0.0, 0
    ok = sum(1 for text, i in pairs if i in corpus.docs and judge(text, corpus.docs[i].text))
    return ok / len(pairs), len(pairs)


def run_evals(models: dict[str, Model] | None = None, corpus: Corpus | None = None,
              evals: list[dict] | None = None, verify: bool = True, **research_kwargs) -> Scorecard:
    corpus = corpus or Corpus.load()
    rows = []
    for ev in evals or load_evals():
        res = research(ev["question"], models=models, corpus=corpus, verify=verify, **research_kwargs)
        rec, missed = fact_recall(res.report, ev["facts"])
        prec, n = citation_precision(res.report, corpus)
        rows.append(EvalRow(ev["id"], ev["question"], rec, prec, len(ev["facts"]) - len(missed),
                            len(ev["facts"]), n, res.cost_usd, res.tokens, missed))
    return Scorecard(rows)


def format_scorecard(card: Scorecard, title: str = "deepresearch evals") -> str:
    lines = [title, "", f"{'id':<5} {'recall':>7} {'cite prec':>9} {'cites':>5} {'tokens':>7} {'cost':>8}  question",
             "-" * 78]
    for r in card.rows:
        q = r.question if len(r.question) <= 34 else r.question[:31] + "..."
        lines.append(f"{r.id:<5} {r.recall:>7.0%} {r.precision:>9.0%} {r.citations:>5} {r.tokens:>7,} "
                     f"${r.cost_usd:>7.4f}  {q}")
    lines += ["-" * 78,
              f"{'all':<5} {card.recall:>7.0%} {card.precision:>9.0%} "
              f"{sum(r.citations for r in card.rows):>5} {sum(r.tokens for r in card.rows):>7,} "
              f"${card.cost_usd:>7.4f}"]
    missed = [(r.id, m) for r in card.rows for m in r.missed]
    if missed:
        lines += ["", "Missed facts:"] + [f"  {i}: {m}" for i, m in missed]
    return "\n".join(lines)
