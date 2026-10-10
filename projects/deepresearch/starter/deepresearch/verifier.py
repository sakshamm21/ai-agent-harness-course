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
    """One claim against one source (doc is Doc.to_dict()). An unreadable reply counts as unsupported.

    One call: verify_prompt(claim, doc) with VERIFIER_SYSTEM. Expect {"supported": bool, "reason": str}.
    """
    raise NotImplementedError("Part 4: ask the verifier about one citation (verify_claim)")


def check_claims(claims: list[Claim], corpus: Corpus, model: Model) -> list[Failure]:
    """Check every (claim, source) pair; return a Failure for each one that fails.

    A source id the corpus does not have is a failure too ("cited document does not exist").
    """
    raise NotImplementedError("Part 4: check every citation (check_claims)")


def drop_failures(claims: list[Claim], failures: list[Failure]) -> tuple[list[Claim], list[str]]:
    """Remove failed (claim, source) citations; a claim with no source left is dropped.

    Returns (kept claims, texts of dropped claims).
    """
    raise NotImplementedError("Part 4: drop citations that still fail (drop_failures)")


def revise(result: WorkerResult, claims: list[Claim], failures: list[Failure], corpus: Corpus,
           model: Model) -> list[Claim]:
    """Send the rejections back to the reviser with the pages the worker read (and nothing else).

    One call: revise_prompt(sub_question, claims as dicts, failures as {"claim","source","reason"},
    pages as Doc.to_dict()) with REVISER_SYSTEM. Parse with parse_claims(text, result.read_ids)
    so the reviser cannot cite unread pages. If the reply has no JSON at all, keep `claims`.
    """
    raise NotImplementedError("Part 4: send failures back to the reviser (revise)")


def verify_and_revise(result: WorkerResult, corpus: Corpus, verifier: Model, reviser: Model,
                      max_rounds: int = 2) -> tuple[WorkerResult, VerifyReport]:
    """Loop check -> revise until clean or max_rounds checks; drop citations that still fail.

    A result that is not ok comes back unchanged. Each round: failures = check_claims(...);
    record report.rounds, report.checked (+ number of citations) and failures_per_round.
    No failures: stop. Last round: drop_failures and stop. Otherwise revise and go again.
    Return (copy of result with the new claims, status "ok" or "empty"), report.
    """
    raise NotImplementedError("Part 4: the evaluator-optimizer loop (verify_and_revise)")
