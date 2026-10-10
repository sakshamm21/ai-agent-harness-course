# deepresearch

Build a multi-agent research assistant in 6 parts. This is capstone 3 of
[Free Agent Harness](https://github.com/sakshamm21/free-agent-harness-course): about 1,500 lines of
standard-library Python.

You ask a question. An orchestrator splits it into sub-questions. Worker agents research them in
parallel with `search` and `fetch_page` over a bundled corpus, all charged to one shared cost cap.
A citation verifier checks every claim against the page it cites and sends bad citations back for
repair. A report writer turns the verified claims into Markdown with numbered sources. Ten eval
questions with reference facts score the whole pipeline on fact recall and citation precision.

It runs offline on a deterministic mock model by default. Set `ANTHROPIC_API_KEY` to use a real
model (planner and writer `claude-sonnet-5-5`, workers, verifier and reviser `claude-haiku-5-5`).

## Quickstart (from a clean clone)

Python 3.10+ is all it needs. The tests need pytest.

```bash
cd projects/deepresearch
python3 -m pip install pytest            # only for the tests

# 1. Ask the finished assistant a question, offline
PYTHONPATH=solution python3 -m deepresearch "When did the Velmora Tunnel open? How long is it?"
PYTHONPATH=solution python3 -m deepresearch --trace "Who operates the Kestrel Ridge wind farm?"

# 2. Run the reference tests (all green) and your starter (red, for now)
IMPL=solution python3 -m pytest -q
IMPL=starter  python3 -m pytest -q

# 3. Score the 10-question eval set, with and without the citation verifier
PYTHONPATH=solution python3 -m deepresearch --eval
PYTHONPATH=solution python3 -m deepresearch --eval --no-verify
```

On the mock, `--eval` scores 100% fact recall and 100% citation precision. With `--no-verify`
recall stays at 100% but citation precision drops to about 58%: that gap is what part 4 buys.

Or install it as a command: `python3 -m pip install -e .` gives you `deepresearch` on your PATH
(it installs `solution/`; edit `pyproject.toml` to install `starter/` instead). Install with `-e`:
the corpus is read from `data/` next to the package. Set `DEEPRESEARCH_DATA` to point elsewhere.

### With a real model

```bash
export ANTHROPIC_API_KEY=sk-ant-...
PYTHONPATH=solution python3 -m deepresearch "What caused the 2022 algae bloom in Lake Mirren?"
PYTHONPATH=solution python3 -m deepresearch --max-usd 0.05 --workers 2 "..."   # tighter cap
DEEPRESEARCH_WORKER_MODEL=claude-sonnet-5-5 PYTHONPATH=solution python3 -m deepresearch --eval
```

Override any role with `DEEPRESEARCH_<ROLE>_MODEL` (`PLANNER`, `WORKER`, `VERIFIER`, `REVISER`,
`WRITER`). `DEEPRESEARCH_MOCK=1` forces the mock even with a key set. The real model is called with
`urllib` (no SDK needed). Cost figures use the illustrative prices in `solution/deepresearch/tokens.py`;
check the provider's pricing page before you trust them. The workers still search the bundled
corpus: the questions are about fictional places, so the reference facts only exist there.

## How the course works

| Folder | What it is |
|---|---|
| `solution/deepresearch/` | The complete assistant. Read it when you are stuck. |
| `starter/deepresearch/` | The same files. Every function you write raises `NotImplementedError("Part N: ...")`. Its docstring is the spec. |
| `tests/test_partNN_*.py` | One test file per part. `IMPL=starter` (default) tests your code; `IMPL=solution` tests the reference. |
| `data/corpus/` | 80 short fictional documents (news, reports, wiki pages) with ids like `vt-01`. |
| `data/evals.jsonl` | 10 questions, each with reference facts and the strings that prove a fact was stated. |

The model, the agent loop, the `@tool` decorator, the prompts and the records are given to you
(`model.py`, `loop.py`, `tools.py`, `prompts.py`, `records.py`). You build the parts below, in
order. Each part's tests only need the parts before it.

```bash
IMPL=starter python3 -m pytest tests/test_part01_orchestrator.py   # make this green, then part 2, ...
```

| Part | File | You build | Test |
|---|---|---|---|
| 1 | `orchestrator.py` | Plan sub-questions, hand them out, replan the ones that fail | `test_part01_orchestrator.py` |
| 2 | `corpus.py`, `worker.py` | BM25 `search`, `fetch_page`, and a worker agent that returns cited claims | `test_part02_workers.py` |
| 3 | `parallel.py` | Workers on a thread pool under one shared, thread-safe cost cap | `test_part03_parallel.py` |
| 4 | `verifier.py` | The citation verifier: an evaluator-optimizer loop | `test_part04_verifier.py` |
| 5 | `writer.py` | A structured handoff to the writer; numbered citations and a Sources list | `test_part05_writer.py` |
| 6 | `evals.py` | Fact recall and citation precision over 10 questions | `test_part06_evals.py` |

The step-by-step guide for each part is on the site at `/p/deepresearch/`.

## CLI reference

```
python3 -m deepresearch [question] [--eval] [--no-verify] [--max-usd USD] [--max-tokens N]
                        [--workers N] [--trace] [--json]
```

The report goes to stdout; a one-line summary (sub-questions, their status, tokens, cost) goes to
stderr. `--trace` prints the orchestrator's events (plan, worker, verify, replan) to stderr.
The default cost cap is $0.50 per question.
