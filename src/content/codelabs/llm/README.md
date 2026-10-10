---
title: "What an LLM Actually Does"
---

## The scenario

An LLM does one thing: given the tokens so far, it scores every possible next token, picks one, appends it, and repeats. You will build that loop on a toy model small enough to read, then watch a model's answer arrive as a stream of pieces.

`NEXT` is the toy model. For each token it lists the probabilities of the next one. After `"The"`, the model thinks `"cat"` is 50% likely, `"dog"` 30% and `"model"` 20%.

## Your task

1. Finish `apply_temperature(probs, t)`. With `t == 0`, give the most likely token probability 1.0 and every other token 0.0. Otherwise raise each probability to the power `1/t` and divide by the total so they sum to 1. Low `t` sharpens the distribution; high `t` flattens it.
2. Finish `generate(t, rng)`. Start from `"<start>"`, sample the next token from `apply_temperature(NEXT[prev], t)`, append it, and stop at `"."`. This loop is how every LLM writes, one token at a time.
3. In the streaming loop at the bottom, append each `text_delta` piece to `pieces` and print it as it arrives. Keep the `done` event's response in `final`.

Press **Run** and compare the `t=0` and `t=1.0` lines. Then try `t=2.0` and see the odd sentences get more common. If you switch on a real model, the streaming part calls it instead of the mock.

## What the checks look for

- `t=0` puts all the probability on the top token, `t=1` changes nothing, `t=0.5` sharpens and still sums to 1.
- `generate` at `t=0` gives the same sentence every time; at `t=1` it gives at least 3 different ones over 20 seeds.
- The streamed pieces join up to exactly the final answer.
