---
title: "Hooks and Lifecycle Events"
realModel: false
---

## The scenario

A scripted coding agent is asked to "switch the app to test keys and tidy up app.py". It makes four `write_file` calls:

1. `.env`: overwrites your live Stripe key.
2. `app.py`: writes code with a tab, trailing spaces and extra blank lines.
3. `config/.env.local`: another secrets file.
4. `docs/environment.md`: a harmless docs page.

You will not change the model or the tools. You will add two **hooks**: small functions the harness calls around every tool call. `run_loop` already accepts them:

- `pre_tool(name, args)` runs **before** the tool. Returning `False` blocks the call; the model gets an error result that says so.
- `post_tool(name, args, result)` runs **after** a successful call. Returning a string replaces the result the model sees; returning `None` keeps it.

## Your task

1. In `pre_tool`, return `False` when `name` is `write_file` and the file name (the last part of the path) is `.env` or starts with `.env.`. Return `None` for everything else.
2. In `post_tool`, when `name` is `write_file` and the path ends with `.py`, run `fmt()` on the file and save it back into `FILES`. Return the original result with `" (auto-formatted)"` added.
3. Press **Run** and read the event list: two writes should show as `blocked`, and `app.py` should come out clean.

## What the checks look for

- `pre_tool` blocks `.env` and `config/.env.local`, and allows `docs/environment.md` and `src/envelope.py`.
- After the run, `.env` still holds the live key and `config/.env.local` was never created.
- `app.py` is formatted, and `post_tool` reports that in its result.
- `post_tool` returns `None` for other tools.
- The transcript contains exactly two error results, one per blocked write, so the model knows.
