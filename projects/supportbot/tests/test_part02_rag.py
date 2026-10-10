"""Part 2: retrieve, answer from the documents, cite [article-id], reject made-up citations."""
from supportbot.model import MockModel, Model, Response
from supportbot.rag import NOT_FOUND, answer, build_messages, check_citations, extract_citations, retrieve


class Scripted(Model):
    """Replies with fixed text and records what it was sent."""

    def __init__(self, text):
        self.text, self.seen = text, []

    def complete(self, messages, tools=None, system=None, temperature=0.0, max_tokens=1024):
        self.seen.append((system, messages))
        return Response(text=self.text)


def test_retrieve_keeps_one_chunk_per_article(index):
    hits = retrieve(index, "How long do refunds take?", k=3)
    ids = [h["article_id"] for h in hits]
    assert 1 <= len(hits) <= 3 and len(ids) == len(set(ids)) and "refund-timing" in ids


def test_retrieve_drops_low_scores(index):
    assert retrieve(index, "zebra quantum xylophone", k=3, min_score=0.3) == []


def test_documents_go_before_the_question():
    hits = [{"article_id": "returns-window", "title": "Our return window", "text": "30 days."}]
    system, messages = build_messages("Can I return this?", hits)
    content = messages[0]["content"]
    assert '<document id="returns-window"' in content
    assert content.index("<document") < content.index("Can I return this?")
    assert "[" in system and "cite" in system.lower()


def test_extract_citations_unique_in_order():
    assert extract_citations("A [b-1]. C [a]. D [b-1].") == ["b-1", "a"]


def test_check_citations_strips_ids_that_were_not_retrieved():
    hits = [{"article_id": "returns-window"}]
    text, valid, invalid = check_citations("30 days [returns-window]. Free forever [made-up].", hits)
    assert valid == ["returns-window"] and invalid == ["made-up"] and "[made-up]" not in text


def test_answer_cites_the_article(index):
    a = answer("Do gift cards expire?", index, MockModel())
    assert "never expire" in a.text and a.citations == ["gift-cards"] and not a.invalid_citations


def test_answer_rejects_a_hallucinated_citation(index):
    model = Scripted("Gift cards never expire [gift-cards]. Also we give free tents [free-tents].")
    a = answer("Do gift cards expire?", index, model)
    assert a.citations == ["gift-cards"] and a.invalid_citations == ["free-tents"] and "[free-tents]" not in a.text


def test_no_documents_means_no_model_call(index):
    model = Scripted("should not be called")
    a = answer("zebra quantum xylophone", index, model)
    assert a.text == NOT_FOUND and model.seen == []
