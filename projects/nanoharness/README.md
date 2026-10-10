# nanoharness

Build your own coding agent harness in 10 parts. This is the flagship capstone of
[Free Agent Harness](https://github.com/sakshamm21/free-agent-harness-course): a small CLI coding agent
in about 930 lines of standard-library Python (about 1,400 counting docstrings and blank lines).

It reads, edits and searches files, runs `bash` in a sandbox with a timeout, asks before writes
and commands, compacts its context at 70% of the window, loads `AGENTS.md`, runs your hooks,
saves every session as JSONL so you can `--resume`, hands reading-heavy jobs to subagents, and
comes with 15 bug-fix evals that report pass rate, turns, tokens and cost.

It runs offline on a scripted mock model by default. Set `ANTHROPIC_API_KEY` to use a real model
(default `claude-sonnet-5-5`).

## Quickstart (from a clean clone)

Python 3.10+ is all the harness needs. The tests need pytest.

```bash
cd projects/nanoharness
python3 -m pip install pytest            # only for the tests

# 1. Try the finished harness on a tiny buggy repo, offline
PYTHONPATH=solution python3 -m nanoharness --init-demo /tmp/nh-demo
cd /tmp/nh-demo
PYTHONPATH=$OLDPWD/solution python3 -m nanoharness --mock "fix the bug in calc.py"
#   answer y to "Allow edit_file: calc.py?" and "Allow bash: python3 -m pytest -q?"
cd -

# 2. Run the reference tests (all green) and your starter (all red, for now)
IMPL=solution python3 -m pytest -q
IMPL=starter  python3 -m pytest -q

# 3. Run the evals on the scripted mock (15/15)
IMPL=solution python3 evals/run_evals.py --mock
```

Or install it as a command: `python3 -m pip install -e .` gives you `nanoharness` on your PATH
(it installs `solution/`; edit `pyproject.toml` to install `starter/` instead).

### With a real model

```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd /path/to/your/repo
nanoharness "the date parser drops the timezone; fix it and add a test"
nanoharness --resume "now update the changelog"        # continue the latest session
NANOHARNESS_MODEL=claude-opus-5-5 nanoharness "..."    # or --model
IMPL=solution python3 evals/run_evals.py --min-pass 10  # the capstone pass bar: 10/15
```

The real model is called with `urllib` (no SDK needed). Requests opt into the API's server-side
refusal fallback. Cost figures use the prices in `solution/nanoharness/model.py`; check the
provider's pricing page before you trust them.

## How the course works

| Folder | What it is |
|---|---|
| `solution/nanoharness/` | The complete harness. Read it when you are stuck. |
| `starter/nanoharness/` | The same files. Every function marked `Part N:` raises `NotImplementedError("Part N: ...")`. Its docstring is the spec. |
| `tests/test_partNN_*.py` | One test file per part. `IMPL=starter` (default) tests your code; `IMPL=solution` tests the reference. |
| `evals/` | `tasks/<name>/` x15 (`task.json` + a tiny `repo/` with a failing pytest) and `run_evals.py`. |
| `scripts/make_starter.py` | Regenerates `starter/` from `solution/` (`--check` to verify they match). |

Work through the parts in order. Each part's tests only need the parts before it.

```bash
IMPL=starter python3 -m pytest tests/test_part01_loop.py      # make this green, then part 2, ...
```

| Part | File | You build | Test |
|---|---|---|---|
| 1 | `loop.py`, `tools.py` | The loop: model call, tool calls, append results, repeat | `test_part01_loop.py` |
| 2 | `tools.py` | `read_file`, `write_file`, `edit_file` (exact replace), `list_dir`, `grep`, locked to the workdir | `test_part02_tools.py` |
| 3 | `permissions.py` | allow / ask / deny rules and a y/N/a prompt | `test_part03_permissions.py` |
| 4 | `sandbox.py` | `bash` in the workdir: timeout, output cap, no secrets, optional `--docker IMAGE` | `test_part04_sandbox.py` |
| 5 | `context.py` | Token counting and compaction by summarization at 70% | `test_part05_context.py` |
| 6 | `instructions.py` | `AGENTS.md` into the system prompt | `test_part06_instructions.py` |
| 7 | `hooks.py` | `pre_tool` / `post_tool` hooks from `nanoharness.json`; exit code 2 blocks | `test_part07_hooks.py` |
| 8 | `session.py` | JSONL transcript and `--resume` | `test_part08_sessions.py` |
| 9 | `subagent.py` | A `task` tool that runs a child loop with a fresh context | `test_part09_subagents.py` |
| 10 | `evals.py` | Grade 15 bug-fix tasks; pass rate, turns, tokens, cost | `test_part10_evals.py` |

The step-by-step guide for each part is on the site at `/p/nanoharness/`.

## Configuration: `nanoharness.json` in the working directory

```json
{
  "permissions": {
    "allow": ["bash(python3 -m pytest*)", "edit_file(src/*)"],
    "ask":   ["bash(git *)"],
    "deny":  ["bash(curl *)", "write_file(.env*)"]
  },
  "hooks": {
    "pre_tool":  [{"matcher": "bash", "command": "python3 .hooks/guard.py"}],
    "post_tool": [{"matcher": "edit_file|write_file", "command": "ruff check --quiet ."}]
  },
  "bash_timeout": 60
}
```

Defaults: read-only tools run freely; `write_file`, `edit_file` and `bash` ask first (`--yes`
approves them); a few destructive commands (`sudo`, `rm -rf /`, `git push`) are always denied.
A hook gets the event as JSON on stdin; a `pre_tool` hook that exits with code 2 blocks the call
and its stderr is the reason the model sees.

## Safety

Local mode is a soft sandbox: commands run in the working directory with secrets stripped from
the environment and a timeout, but a command can still reach the rest of your machine. File
tools refuse paths outside the working directory. For untrusted tasks use `--docker IMAGE`
(only the working directory is mounted and the network is off). Evals always run on a throwaway
copy of each task repo.

## CLI reference

```
nanoharness [prompt ...] [--mock] [--model ID] [-y/--yes] [-C DIR] [--resume] [--session ID]
            [--docker IMAGE] [--max-turns N] [--config FILE] [--init-demo DIR] [-q]
```

With no prompt it starts an interactive session (`exit` or Ctrl-D to quit). Sessions are saved
under `.nanoharness/sessions/` in the working directory.
