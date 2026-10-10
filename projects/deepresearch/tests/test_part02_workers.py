"""Part 2: the corpus, the search and fetch_page tools, and one worker agent."""
import json

import pytest

from deepresearch.model import MockModel, ResearchMock, Response, ToolCall
from deepresearch.worker import make_tools, parse_claims, run_worker


def test_corpus_has_about_80_documents_with_stable_ids_and_urls(corpus):
    assert 70 <= len(corpus) <= 100
    for d in corpus.docs.values():
        assert d.url.startswith("corpus://") and d.title and d.text
    assert len({d.url for d in corpus.docs.values()}) == len(corpus)


def test_search_ranks_the_relevant_document_first(corpus):
    assert corpus.search("velmora tunnel cost")[0]["id"] == "vt-03"
    assert corpus.search("kestrel ridge turbines")[0]["id"] == "kw-01"
    assert corpus.search("orbis 7 launched")[0]["id"] == "ob-01"


def test_search_returns_hits_with_id_title_url_snippet(corpus):
    hits = corpus.search("lake mirren swimming ban", k=3)
    assert len(hits) == 3
    assert set(hits[0]) == {"id", "title", "url", "snippet"}
    assert "swimming" in hits[0]["snippet"].lower()


def test_search_is_deterministic_and_empty_for_unknown_words(corpus):
    assert corpus.search("merrow vaccine") == corpus.search("merrow vaccine")
    assert corpus.search("zzzz qqqq") == []


def test_fetch_by_id_or_url(corpus):
    d = corpus.fetch("cb-03")
    assert "brine" in d.text
    assert corpus.fetch(d.url).id == "cb-03"
    with pytest.raises(KeyError):
        corpus.fetch("nope-99")


def test_tools_have_schemas_the_model_can_read(corpus):
    search, fetch_page = make_tools(corpus)
    assert search.name == "search" and fetch_page.name == "fetch_page"
    assert search.schema["input_schema"]["required"] == ["query"]
    assert fetch_page.schema["input_schema"]["required"] == ["doc_id"]
    assert search(query="harrow point lighthouse")[0]["id"].startswith("hp-")
    assert fetch_page(doc_id="hp-03")["id"] == "hp-03"


def test_parse_claims_keeps_only_sources_the_worker_read():
    text = json.dumps({"claims": [
        {"text": "A.", "sources": ["vt-01", "vt-09"]},
        {"text": "B.", "sources": ["kw-01"]},
        {"text": "", "sources": ["vt-01"]},
    ]})
    claims = parse_claims(text, read_ids=["vt-01"])
    assert [(c.text, c.sources) for c in claims] == [("A.", ["vt-01"])]


def test_parse_claims_handles_junk():
    assert parse_claims("no json here", ["vt-01"]) == []


def test_worker_searches_fetches_and_returns_cited_claims(corpus):
    r = run_worker("How much did it cost (Velmora Tunnel)?", ResearchMock("small"), corpus)
    assert r.status == "ok"
    assert "vt-03" in r.read_ids
    assert r.claims and all(set(c.sources) <= set(r.read_ids) for c in r.claims)
    assert any("6.2 billion" in c.text for c in r.claims)
    assert r.input_tokens > 0 and r.output_tokens > 0


def test_worker_drops_citations_to_pages_it_never_fetched(corpus):
    m = MockModel([
        Response(tool_calls=[ToolCall("c1", "fetch_page", {"doc_id": "am-02"})]),
        Response(text=json.dumps({"claims": [
            {"text": "Amberline cells last 6,000 charge cycles.", "sources": ["am-02"]},
            {"text": "Corvane Cells makes Amberline.", "sources": ["am-03"]},
        ]})),
    ])
    r = run_worker("How many cycles?", m, corpus)
    assert [c.sources for c in r.claims] == [["am-02"]]


def test_worker_survives_a_bad_fetch(corpus):
    m = MockModel([
        Response(tool_calls=[ToolCall("c1", "fetch_page", {"doc_id": "made-up-1"})]),
        Response(text='{"claims": []}'),
    ])
    r = run_worker("anything", m, corpus)
    assert r.status == "empty" and r.read_ids == []
