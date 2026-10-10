"""Part 4: the citation verifier, an evaluator-optimizer loop with a round limit."""
import json

from deepresearch.model import MockModel, ResearchMock, Response
from deepresearch.records import Claim, Failure, WorkerResult
from deepresearch.verifier import check_claims, drop_failures, verify_and_revise, verify_claim

GOOD = "The Velmora Tunnel cost 6.2 billion crowns to build, according to the final audit published by the Halden Rail Authority."
OTHER = "The Velmora Tunnel is 31.4 kilometres long, of which 24.1 kilometres run beneath the Halden Strait."


def test_verify_claim_accepts_a_source_that_states_the_claim(corpus):
    assert verify_claim(GOOD, corpus.fetch("vt-03").to_dict(), ResearchMock()).supported


def test_verify_claim_rejects_the_wrong_source(corpus):
    v = verify_claim(GOOD, corpus.fetch("vt-01").to_dict(), ResearchMock())
    assert not v.supported and v.reason


def test_verify_claim_treats_an_unreadable_reply_as_unsupported(corpus):
    v = verify_claim(GOOD, corpus.fetch("vt-03").to_dict(), MockModel([Response(text="Looks fine to me!")]))
    assert not v.supported


def test_check_claims_lists_each_bad_citation(corpus):
    claims = [Claim(GOOD, ["vt-03", "vt-01"]), Claim(OTHER, ["vt-02"]), Claim(OTHER, ["zz-99"])]
    fails = check_claims(claims, corpus, ResearchMock())
    assert {(f.claim, f.source) for f in fails} == {(GOOD, "vt-01"), (OTHER, "zz-99")}


def test_drop_failures_removes_citations_then_empty_claims():
    claims = [Claim("a", ["x", "y"]), Claim("b", ["x"])]
    kept, dropped = drop_failures(claims, [Failure("a", "x", ""), Failure("b", "x", "")])
    assert [(c.text, c.sources) for c in kept] == [("a", ["y"])] and dropped == ["b"]


def _misattributed():
    # The mock worker's habit: cite the first page read for everything.
    return WorkerResult("How much did it cost (Velmora Tunnel)?", "ok",
                        [Claim(GOOD, ["vt-02"]), Claim(OTHER, ["vt-02"])], read_ids=["vt-02", "vt-03"])


def test_verifier_sends_failures_back_and_the_reviser_fixes_them(corpus):
    fixed, rep = verify_and_revise(_misattributed(), corpus, ResearchMock(), ResearchMock(), max_rounds=3)
    assert rep.failures_per_round == [1, 0]
    assert rep.rounds == 2 and not rep.dropped
    by_text = {c.text: c.sources for c in fixed.claims}
    assert by_text == {GOOD: ["vt-03"], OTHER: ["vt-02"]}


def test_round_limit_drops_what_still_fails(corpus):
    stubborn = MockModel([Response(text=json.dumps({"claims": [{"text": GOOD, "sources": ["vt-02"]},
                                                               {"text": OTHER, "sources": ["vt-02"]}]}))])
    fixed, rep = verify_and_revise(_misattributed(), corpus, ResearchMock(), stubborn, max_rounds=2)
    assert rep.rounds == 2 and rep.failures_per_round == [1, 1]
    assert stubborn.calls == 1, "revise between checks, never after the last one"
    assert [c.text for c in fixed.claims] == [OTHER] and rep.dropped == [GOOD]


def test_reviser_cannot_cite_pages_the_worker_did_not_read(corpus):
    sneaky = MockModel([Response(text=json.dumps({"claims": [{"text": GOOD, "sources": ["vt-03"]}]}))])
    r = WorkerResult("q", "ok", [Claim(GOOD, ["vt-02"])], read_ids=["vt-02"])
    fixed, _ = verify_and_revise(r, corpus, ResearchMock(), sneaky, max_rounds=2)
    assert fixed.claims == [] and fixed.status == "empty"


def test_clean_results_pass_in_one_round(corpus):
    r = WorkerResult("q", "ok", [Claim(GOOD, ["vt-03"])], read_ids=["vt-03"])
    fixed, rep = verify_and_revise(r, corpus, ResearchMock(), ResearchMock())
    assert rep.rounds == 1 and rep.failures_per_round == [0] and fixed.claims == r.claims
