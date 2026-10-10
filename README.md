# Free Agent Harness

**Learn AI agents by building them.** A free, static, hands-on course on AI agents and agent harnesses: 54 lessons in 8 sections, an in-browser Agent Lab for every concept, Python code labs that run in your browser, and three capstone projects you build end to end.

Inspired by the format of [freesystemdesign.com](https://freesystemdesign.com/): every lesson tells one story (problem → insight → fix → math → tradeoff) and ends with a page where you build it and watch it break.

## What's inside

| Path | What |
|---|---|
| `src/content/lessons/` | 54 lessons (MDX). Frontmatter schema in `src/content.config.ts`. |
| `src/content/scenarios/` | Agent Lab scenarios (JSON), one per lab lesson. |
| `src/content/codelabs/` | Python code labs: README, starter, solution, hidden checks. |
| `src/content/projects/` | Capstone pages (`/p/<project>/<part>/`). |
| `src/lab/` | The Agent Lab simulation engine: pure TypeScript, deterministic, unit tested. |
| `src/components/lab/` | The Agent Lab UI (React + React Flow). |
| `src/components/codelab/` | The code lab UI (Pyodide, loaded on first Run). |
| `python/agentkit_mini/` | The tiny agent toolkit the code labs use (mock model, tools, loop, embeddings, MCP). |
| `projects/` | Capstones: `nanoharness` (coding agent harness), `supportbot` (support agent with RAG), `deepresearch` (multi-agent research). |
| `docs/PLAN.md` | The full product spec. |
| `AUTHORING.md` | How to write lessons, scenarios, code labs and capstone pages. |

## Take the course on your computer

The course runs entirely on your machine; there is no hosted version to sign up for.

You need [Node.js](https://nodejs.org/) 22 or newer and git. Python 3.12 is only needed for the capstone projects.

```bash
git clone https://github.com/sakshamm21/free-agent-harness-course.git
cd free-agent-harness-course
npm install
npm run dev          # open http://localhost:4321
```

Lessons, Agent Labs and code labs all work in `npm run dev`. Search needs a built copy:

```bash
npm run build && npm run preview      # http://localhost:4321, search included
```

Your progress is tracked automatically: lessons you mark complete, labs and code labs you pass, and capstone
parts you finish are ticked off on the home and project pages, along with your lab graphs and code lab code.
It is saved in your browser for `http://localhost:4321`, so it survives restarting the server or the computer.
Two things to know:

- Always open the same address. `localhost:4321` and `127.0.0.1:4321` (or another port, if 4321 was busy) are
  different sites to the browser and keep separate progress.
- Clearing your browser's site data erases it. To back it up or move it to another browser or computer, use
  **Your progress** in the footer: download a file, import it on the other side.

Capstone projects are plain Python in `projects/`; each has a README with its own steps, for example:

```bash
cd projects/nanoharness
python3 -m pip install pytest
python3 -m pytest -q          # your starter code: fails until you build each part
IMPL=solution python3 -m pytest -q   # the reference solution: passes
```

To get new lessons later: `git pull && npm install`.

## Checks

For contributors (all run in CI):

```bash
node scripts/validate-content.mjs           # lesson frontmatter, MDX, structure
npm test                                    # lab engine + every scenario (starter fails, solution passes)
PYTHONPATH=python python3 -m pytest python/tests
python3 scripts/check_codelabs.py           # every code lab (starter fails, solution passes)
npm run build && npm run check              # static build + internal link check
(cd projects/nanoharness && IMPL=solution python3 -m pytest -q)
```

## Hosting (optional, later)

Not needed to take the course. If you ever want a public copy, see [DEPLOY.md](DEPLOY.md).

## Licence

Lesson content: CC BY-NC-SA 4.0. Code: MIT. See `LICENSE` and `LICENSE-CONTENT`.
