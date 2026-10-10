"""Part 6: evals: 10 questions, reference facts, fact recall and citation precision."""
from deepresearch.evals import citation_precision, fact_recall, format_scorecard, load_evals, run_evals

REPORT = """# Q

- The Velmora Tunnel opened to passenger trains on 14 June 2019 [1].
- The Velmora Tunnel cost 6.2 billion crowns to build [1].

## Sources

1. Velmora Tunnel opens to passenger trains. Northbay Gazette, 2019-06-14. <corpus://x> (vt-01)
"""


def test_eval_set_has_ten_questions_with_reference_facts():
    evals = load_evals()
    assert len(evals) == 10 and len({e["id"] for e in evals}) == 10
    for e in evals:
        assert e["question"] and len(e["facts"]) >= 2
        assert all(f["fact"] and f["match"] for f in e["facts"])


def test_reference_facts_are_in_the_corpus(corpus):
    text = " ".join(d.text for d in corpus.docs.values()).lower()
    for e in load_evals():
        for f in e["facts"]:
            assert all(m.lower() in text for m in f["match"]), f["fact"]


def test_fact_recall():
    facts = [{"fact": "opened 2019", "match": ["2019"]}, {"fact": "31.4 km", "match": ["31.4"]},
             {"fact": "cost", "match": ["6.2 billion", "crowns"]}]
    rec, missed = fact_recall(REPORT, facts)
    assert abs(rec - 2 / 3) < 1e-9 and missed == ["31.4 km"]


def test_fact_recall_ignores_the_sources_list():
    rec, _ = fact_recall(REPORT, [{"fact": "gazette", "match": ["Northbay Gazette"]}])
    assert rec == 0


def test_citation_precision_checks_each_citation_against_its_document(corpus):
    prec, n = citation_precision(REPORT, corpus)
    assert n == 2 and prec == 0.5  # vt-01 does not say what the tunnel cost


def test_citation_precision_of_an_uncited_report_is_zero(corpus):
    assert citation_precision("# Q\n\nNo cites here.\n", corpus) == (0.0, 0)


def test_scorecard_on_the_mock(models, corpus):
    card = run_evals(models, corpus)
    assert len(card.rows) == 10
    assert card.recall >= 0.8, format_scorecard(card)
    assert card.precision >= 0.95, format_scorecard(card)
    out = format_scorecard(card)
    assert "q10" in out and "all" in out


def test_the_verifier_raises_citation_precision(models, corpus):
    evals = load_evals()[:4]
    with_v = run_evals(models, corpus, evals, verify=True)
    without = run_evals(models, corpus, evals, verify=False)
    assert with_v.precision > without.precision + 0.2
    assert with_v.recall >= without.recall - 0.1
