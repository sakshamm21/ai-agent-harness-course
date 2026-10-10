---
title: "Embeddings and Similarity"
realModel: false
---

## The scenario

A shop has **50 FAQs**. Customers never use the FAQ's words: they type "terminate membership", not "cancel my subscription", and "the lamp arrived faulty", not "my item arrives broken". The current search counts shared words and finds the right FAQ for only 2 of the 8 test queries.

You will replace it with semantic search: turn every FAQ into a vector with the bundled `embed()` model, turn the query into a vector, and rank FAQs by cosine similarity.

The bundled model is tiny and runs in your browser. It hashes words and three-letter pieces of words into 256 numbers, plus a small synonym table ("refund" and "reimburse" share a feature). A real embedding model learns these relations from billions of sentences, but the search code you write is the same.

## Your task

1. Finish `cosine(a, b)`: the dot product of the two vectors divided by the product of their lengths. It returns 1 for the same direction, 0 for unrelated, -1 for opposite.
2. Finish `build_index(faqs)`: embed each FAQ once, using its question and answer together, and return a list of `(id, vector)`.
3. Finish `semantic_search(query, index, k)`: embed the query, score every FAQ with `cosine`, and return the `k` best ids, best first.
4. Press **Run** and compare the two hit rates. Look at the one query semantic search still misses, and work out why.

## What the checks look for

- `cosine` gives 1, 0 and -1 for same, perpendicular and opposite vectors, even when they are not unit length.
- The index holds 50 vectors of 256 numbers.
- `semantic_search` returns `k` ids, best first, and puts `password-reset` first for "i can't log in".
- Semantic search finds the right FAQ in the top 3 for at least 75% of test queries, and beats keyword search.
