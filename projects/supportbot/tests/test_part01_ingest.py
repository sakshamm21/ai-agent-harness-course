"""Part 1: articles -> chunks -> vectors -> a searchable index."""
from conftest import HELP, POISONED

from supportbot.ingest import VectorIndex, chunk_article, cosine, embed, load_articles, parse_article


def test_parse_article_reads_front_matter():
    a = parse_article(HELP / "returns-window.md")
    assert a["id"] == "returns-window" and a["title"] == "Our return window" and a["category"] == "returns"
    assert a["body"].startswith("# Our return window") and "---" not in a["body"]


def test_parse_article_needs_an_id(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("---\ntitle: No id\n---\nBody.\n")
    try:
        parse_article(p)
    except ValueError:
        return
    raise AssertionError("an article without an id must raise ValueError")


def test_the_help_center_has_60_articles_with_unique_ids():
    arts = load_articles(HELP)
    assert len(arts) == 60 and len({a["id"] for a in arts}) == 60


def test_chunks_respect_the_word_limit_and_keep_the_title():
    article = {"id": "x", "title": "Tent care", "body": " ".join(f"Sentence number {i} is here." for i in range(30))}
    chunks = chunk_article(article, max_words=20, overlap=1)
    assert len(chunks) > 1
    assert [c["chunk_id"] for c in chunks][:2] == ["x#0", "x#1"]
    for c in chunks:
        title, _, body = c["text"].partition("\n")
        assert title == "Tent care" and c["article_id"] == "x" and len(body.split()) <= 20


def test_chunks_overlap_by_one_sentence():
    article = {"id": "x", "title": "T", "body": " ".join(f"Sentence number {i} is here." for i in range(12))}
    a, b = chunk_article(article, max_words=15, overlap=1)[:2]
    last_of_a = a["text"].split("\n", 1)[1].split(". ")[-1].rstrip(".")
    assert b["text"].split("\n", 1)[1].startswith(last_of_a)


def test_short_article_is_one_chunk_without_the_heading():
    chunks = chunk_article(parse_article(HELP / "sales-tax.md"))
    assert len(chunks) == 1 and "#" not in chunks[0]["text"]


def test_embeddings_are_unit_length_and_deterministic():
    v = embed("How long do refunds take?")
    assert abs(sum(x * x for x in v) - 1) < 1e-9 and v == embed("How long do refunds take?")
    assert cosine(v, v) > 0.999


def test_similar_texts_score_higher_than_unrelated_ones():
    q = embed("when will I get my money back")
    assert cosine(q, embed("Refunds take 5 to 10 business days")) > cosine(q, embed("Tent poles are aluminium"))


def test_search_finds_the_right_article(index):
    for question, article in [("How many days do I have to return an item?", "returns-window"),
                              ("how do I wash my rain jacket", "jacket-care"),
                              ("do you ship to Canada", "international-shipping"),
                              ("I forgot my password", "reset-password")]:
        top = index.search(question, k=3)
        assert article in [h["article_id"] for h in top], (question, [h["article_id"] for h in top])


def test_search_returns_k_scored_hits_best_first(index):
    hits = index.search("gift card balance", k=4)
    assert len(hits) == 4 and hits[0]["article_id"] == "gift-cards"
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)


def test_index_saves_and_loads(index, tmp_path):
    index.save(tmp_path / "index.json")
    again = VectorIndex.load(tmp_path / "index.json")
    assert len(again) == len(index)
    assert again.search("student discount", k=1)[0]["article_id"] == "student-discount"


def test_poisoned_article_is_ingested_like_any_other(poisoned_index, index):
    assert len(poisoned_index) > len(index)
    assert POISONED.exists()
