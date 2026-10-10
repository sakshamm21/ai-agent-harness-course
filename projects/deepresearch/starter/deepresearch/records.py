"""The structured records agents hand to each other. Plain dataclasses, JSON-friendly."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Claim:
    text: str
    sources: list[str]  # doc ids, e.g. ["vt-03"]

    def to_dict(self) -> dict:
        return {"text": self.text, "sources": list(self.sources)}


@dataclass
class WorkerResult:
    sub_question: str
    status: str = "ok"  # ok | empty | failed | budget | skipped
    claims: list[Claim] = field(default_factory=list)
    read_ids: list[str] = field(default_factory=list)  # pages the worker fetched
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class Failure:
    """One citation the verifier rejected."""
    claim: str
    source: str
    reason: str


@dataclass
class Verdict:
    supported: bool
    reason: str = ""


@dataclass
class VerifyReport:
    rounds: int = 0
    checked: int = 0
    failures_per_round: list[int] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    question: str
    report: str
    sub_questions: list[str]
    results: list[WorkerResult]
    partial: bool = False
    cost_usd: float = 0.0
    tokens: int = 0
    verify: list[VerifyReport] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
