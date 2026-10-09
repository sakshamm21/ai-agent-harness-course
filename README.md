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

## Run it locally

```bash
npm install
npm run dev          # http://localhost:4321
```

Checks (all run in CI):

```bash
node scripts/validate-content.mjs           # lesson frontmatter, MDX, structure
npm test                                    # lab engine + every scenario (starter fails, solution passes)
PYTHONPATH=python python3 -m pytest python/tests
python3 scripts/check_codelabs.py           # every code lab (starter fails, solution passes)
npm run build && npm run check              # static build + internal link check
(cd projects/nanoharness && IMPL=solution python3 -m pytest -q)
```

## Deploy (free)

See [DEPLOY.md](DEPLOY.md). Short version: Cloudflare Pages, build command `npm run build`, output directory `dist`.

## Licence

Lesson content: CC BY-NC-SA 4.0. Code: MIT. See `LICENSE` and `LICENSE-CONTENT`.
