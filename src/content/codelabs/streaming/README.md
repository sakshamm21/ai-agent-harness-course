---
title: "Streaming and UX"
realModel: false
---

## The scenario

A support bot answers **"Where is my order 4417?"**. It takes 3 turns: look up the order, look up the tracking scan, then answer. Right now the harness waits for each full response before it shows anything, and the tool calls happen silently. The user stares at a blank box.

`Model.stream()` already yields events as the reply is generated: `{"type": "text_delta", "text": ...}` for each chunk, then `{"type": "tool_use", ...}` for any tool calls, then `{"type": "done", "response": ...}`. `run_loop` already calls `on_event` for every model turn and tool call. You will connect them to the screen.

## Your task

1. Finish `status_line(event)`. Return a short line for the events a user cares about: a `model` event with `tool_calls` ("Looking up: lookup_order..."), `tool` ("✓ lookup_order"), `tool_error` ("✗ lookup_order failed") and `done` ("Answer ready (3 turns)"). Return `None` for anything else.
2. Finish `Streaming.complete()`. Loop over `self.inner.stream(...)`. For each `text_delta`, add it to `text`, add 1 to `self.shown`, append `("text", chunk)` to `TIMELINE` and print it with `end=""`. On `done`, return `ev["response"]`.
3. Add the Stop button. When `self.stop_after` is set and `self.shown` reaches it, return `Response(text=text.rstrip() + " [stopped]")` straight away. It has no tool calls, so the loop treats it as the final answer and stops.
4. Press **Run**. The first words should appear before any status line, and the second run should stop mid-sentence.

## What the checks look for

- `status_line` returns a line that names the tool for tool requests, results and failures, and gives the turn count for `done`.
- The answer reaches `TIMELINE` as 20 or more chunks that together contain the final answer.
- Text and status lines are interleaved: words, then a status line, then more words.
- The stopped run ends with `[stopped]` after 2 turns, and `get_tracking` never runs.
