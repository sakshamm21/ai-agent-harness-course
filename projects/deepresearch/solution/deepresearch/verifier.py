"""Part 4: the citation verifier, an evaluator-optimizer loop.

Evaluator: a verifier model reads one claim and the one document it cites, and says
supported or not. Optimizer: the worker's claims and the rejections go to a reviser,
which re-cites each rejected claim to a page that does state it, or drops it.
Repeat until every citation passes or max_rounds runs out; then drop what still fails.
"""
from __future__ import annotations

from dataclasses import replace

from .corpus import Corpus
from .model import Model
from .prompts import REVISER_SYSTEM, VERIFIER_SYSTEM, revise_prompt, verify_prompt
from .records import Claim, Failure, Verdict, VerifyReport, WorkerResult
from .textutil import extract_json
from .worker import parse_claims


def verify_claim(claim: str, doc: dict, model: Model) -> Verdict:
    """One claim against one source. An unreadable reply counts as unsupported."""
    resp = model.complete([{"role": "user", "content": verify_prompt(claim, doc)}], system=VERIFIER_SYSTEM)
    data = extract_json(resp.text)
    if not isinstance(data, dict) or "supported" not in data:
        return Verdict(False, "verifier reply was not valid JSON")
    ok = data["supported"]
    ok = ok if isinstance(ok, bool) else str(ok).strip().lower() == "true"
    return Verdict(ok, str(data.get("reason", "")))


def check_claims(claims: list[Claim], corpus: Corpus, model: Model) -> list[Failure]:
    """Check every (claim, source) pair. Returns the pairs that failed."""
    failures = []
    for c in claims:
        for src in c.sources:
            try:
                doc = corpus.fetch(src).to_dict()
            except KeyError:
                failures.append(Failure(c.text, src, "cited document does not exist"))
                continue
            v = verify_claim(c.text, doc, model)
            if not v.supported:
                failures.append(Failure(c.text, src, v.reason))
    return failures


def drop_failures(claims: list[Claim], failures: list[Failure]) -> tuple[list[Claim], list[str]]:
    """Remove failed citations; a claim with no citation left is removed too."""
    bad = {(f.claim, f.source) for f in failures}
    kept, dropped = [], []
    for c in claims:
        srcs = [s for s in c.sources if (c.text, s) not in bad]
        if srcs:
            kept.append(Claim(c.text, srcs))
        else:
            dropped.append(c.text)
    return kept, dropped


def revise(result: WorkerResult, claims: list[Claim], failures: list[Failure], corpus: Corpus,
           model: Model) -> list[Claim]:
    """Send the rejections back. The reviser sees the pages the worker read and nothing else."""
    pages = [corpus.fetch(i).to_dict() for i in result.read_ids if i in corpus.docs]
    prompt = revise_prompt(result.sub_question, [c.to_dict() for c in claims],
                           [{"claim": f.claim, "source": f.source, "reason": f.reason} for f in failures], pages)
    resp = model.complete([{"role": "user", "content": prompt}], system=REVISER_SYSTEM)
    revised = parse_claims(resp.text, result.read_ids)
    return revised if extract_json(resp.text) is not None else claims


def verify_and_revise(result: WorkerResult, corpus: Corpus, verifier: Model, reviser: Model,
                      max_rounds: int = 2) -> tuple[WorkerResult, VerifyReport]:
    """Loop check -> revise until clean or max_rounds checks; drop citations that still fail."""
    report = VerifyReport()
    claims = list(result.claims)
    if not result.ok:
        return result, report
    for rnd in range(1, max_rounds + 1):
        failures = check_claims(claims, corpus, verifier)
        report.rounds = rnd
        report.checked += sum(len(c.sources) for c in claims)
        report.failures_per_round.append(len(failures))
        if not failures:
            break
        if rnd == max_rounds:
            claims, report.dropped = drop_failures(claims, failures)
            break
        claims = revise(result, claims, failures, corpus, reviser)
    status = "ok" if claims else "empty"
    return replace(result, claims=claims, status=status), report
