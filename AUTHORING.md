# Authoring guide

How to write lessons, Agent Lab scenarios, code labs and capstone pages for Free Agent Harness. Read this before adding content. The full product spec is `docs/PLAN.md`.

## Commands

```bash
npm run dev                          # local site at http://localhost:4321
npm test                             # vitest: engine tests + every scenario (starter fails, solution passes)
npx vite-node scripts/sim.ts <id>    # print starter vs solution metrics for one scenario
python3 scripts/check_codelabs.py    # every code lab: starter fails, solution passes (CPython)
npm run build                        # full static build into dist/ (fails on bad frontmatter or missing labs)
npm run check                        # internal link check over dist/
```

## 1. Lessons: `src/content/lessons/<slug>.mdx`

The filename is the slug and the URL (`/c/<slug>/`). Frontmatter is validated by `src/content.config.ts`; the build fails on any mistake.

```yaml
---
title: "The Agent Loop"
section: "tools"          # foundations | tools | harness | memory | patterns | reliability | operate | cases
order: 9                  # global lesson number 1..54, drives prev/next
tagline: "One line."
realWorld: "Short real-world example"
build:
  type: "lab"             # lab | code | none
  scenario: "agent_loop"  # optional; defaults to the slug. lab -> src/content/scenarios/<id>.json, code -> src/content/codelabs/<id>/
terms:                    # feeds /glossary/. 2-4 terms, each with a one-sentence definition
  - term: "agent loop"
    def: "..."
usedIn: ["nanoharness/1"] # capstone parts that use this lesson (project/part)
readingMinutes: 6
updated: 2026-10-09
quiz:                     # exactly 3 questions; answer is the 0-based index of the right option
  - q: "..."
    options: ["...", "...", "..."]
    answer: 1
    why: "One or two sentences."
reading:                  # 1-3 further-reading links, real URLs you are confident exist
  - title: "..."
    url: "https://..."
---
```

### Body: the arc (must match)

4 to 6 `##` sections in this order:

1. **The problem**: a concrete failing situation with a number in the first two sentences.
2. **The insight**: why it fails.
3. **The fix**: the mechanism, with one diagram (`<Flow>`, `<Stack>` or inline SVG).
4. **Let us check the math**: tokens, $, latency or success rate, worked through. Put the working in `<Callout type="math" label="Let us check the math">`.
5. **The tradeoff**: what the fix costs you, with 2 or 3 mitigations, linking to the lessons that cover them.
6. Optional **In the real world**: one named system and how it does this (public information only; say "like" when inferring).

Headings are statements, not labels: `## You asked it to fix a bug. It answered with a guess.` is better than `## The problem`. The math and tradeoff headings can be literal ("Let us check the math", "The tradeoff: ...").

`src/content/lessons/agent_loop.mdx` is the reference lesson. Match its length, tone and structure.

### Style

- Second person, present tense, short sentences, one idea per section.
- 600 to 1,000 words. Code snippets 20 lines or fewer.
- Every lesson has a worked calculation with real arithmetic that adds up.
- End on the tradeoff, never "and that's it". No marketing adjectives. No em-dashes in headings (avoid them in body text too; use commas, colons or full stops).
- Use real product names only for publicly documented behaviour.
- Use "sim prices" consistently when quoting $: small $1/$5, medium $3/$15, large $15/$75 per million input/output tokens. Say they are illustrative.
- Link other lessons with absolute paths: `[Context management](/c/context_mgmt/)`. Only link slugs that exist in the curriculum (see `docs/PLAN.md` §3).

### Components available in MDX (no import needed)

```mdx
<Flow steps={["User", { label: "Model", sub: "decides", kind: "hl" }, "Tools"]} loop loopLabel="repeat" caption="..." />
<Stack blocks={[{ label: "System", tokens: 2000 }, { label: "History", tokens: 9000, kind: "bad" }]} budget={8000} caption="..." />
<Callout type="math" label="Let us check the math">...</Callout>   {/* type: note | math | warn */}
```

`kind` is `hl` (accent), `bad` (red) or `good` (green). Inline `<svg>` is fine too: use the classes `dg-box`, `dg-text`, `dg-sub`, `dg-line`, `dg-arrow` so it follows the theme. Inside `<Callout>` use `<br />` or blank lines for line breaks; Markdown bold works.

MDX gotchas: `{` `}` and `<` in prose must be escaped or put in backticks (`` `a < b` ``); a bare `<5` breaks the build.

## 2. Agent Lab scenarios: `src/content/scenarios/<id>.json`

The lab is a deterministic simulation. The learner wires nodes on a canvas; the engine (`src/lab/engine.ts`) runs every task for seeds 1..`runs` and checks goals. The "model" is a weighted random policy over **actions** you define. **Modifiers** change those weights based on what is wired and on live state. Schema: `src/lab/schema.ts`. Types and every field: `src/lab/types.ts`. Reference scenario: `agent_loop.json`.

Each scenario must:
- Have a `starter` graph that **fails at least one goal** and a `solution` graph that **passes all goals** (vitest enforces both).
- Only use node types listed in its `palette` (plus `user`).
- Teach the lesson's point: the change from starter to solution should be the lesson's fix, and the failure should be visible in the transcript.
- Have 2 or 3 hints; the last one is nearly the answer. `explain` is one or two sentences shown on pass.
- Aim for margin: solution passes with room (for example 0.93 against a 0.85 bar) so small engine changes don't flip it.

### How a task runs (engine semantics)

Per task: the context starts at `systemTokens` (default 1200) + 200. Each turn:

1. If `outageRate` rolls, the primary model errors. With a `fallback` node the turn continues on the fallback; without one the turn is lost (+30s), and 3 outages fail the task (`outage`).
2. Weights = `policy.base`, then each modifier whose `when` matches applies `set`, then `shift` (add), then `scale` (multiply). Negative weights become 0. Built-ins: a `tool` action whose tool node is missing gets weight 0; a needed tool that already succeeded is scaled by 0.2; `repeat` needs a previous action.
3. One action is sampled and billed: input = current context, output = `outputTokens` (default 150), at the model tier's sim price. Latency += tier latency + `latencyMs`.
4. The action's effect (below). It adds `tokens` (default 300; `task.tokensPerTurn` overrides) to the context.
5. Compaction: if a `compactor` exists and context > `trigger` × window, it compacts (`summarize`: big shrink, small cost; `truncate`: shrinks but sets `lost_instructions`; `offload`: big shrink, +0.5s). A `memory` node with kind `summary` acts like a summarize compactor at 90%. If context still exceeds the window, it is clipped and `over_budget` + `lost_instructions` are set.
6. Stop: `loop.maxCost` (if > 0) exceeded, or turn ≥ `loop.maxTurns` → `stopped`. If `maxTurns` ≥ `hardCap` (default 60) and the cap is hit → `runaway` incident. **Without a `loop` node the task gets exactly one turn**, and any tool request ends it as `stopped`.

Action kinds:

| kind | effect |
|---|---|
| `tool` | Needs a wired tool node with that exact `name`. Interceptors first (permissions deny/ask, guardrail if `guardTag`, approval if `irreversible`); blocked → no progress. Tool `errorRate` (node data) may fail it: `errorMode: raw` adds 900 tokens and sets `tool_error_raw`, `actionable` adds 120 and sets `tool_error_actionable`. Success marks the tool `called` and, when all `task.needs` are called, sets `ready`. `untrusted: true` sets `injected`. `sideEffect: true` + an error may leave a hidden effect; the next success then duplicates it (incident) unless the tool node has `idempotent: true`. `batch: n` = n independent calls: sequential (n turns of latency, n bills) unless the model has `parallelTools: true` (one turn). `offloadable: true` + a `subagent` node → only 15% of the tokens enter the context. |
| `answer` | Ends the task as `correct` or `wrong` (`correct` flag). With a `judge` node: wrong answers are caught with probability 0.25 + 0.7 × passBar (correct ones falsely rejected only when passBar > 0.85), up to `maxRetries`, setting `judged_fail` and continuing. An answer with `incident` set (for example leaking PII) is an incident unless a guardrail with a matching `guardTag` rule blocks it (then the loop continues). |
| `think` | Adds tokens, no progress (planning, reasoning). |
| `repeat` | Adds tokens, no progress, sets `repeating`. |
| `injection`, `dangerous` | Goes through interceptors: permissions deny (by `tool`), guardrail (if rules empty or include `guardTag`, blocks 97%), approval node (always intercepts these; a human denies unless `legit`). Not intercepted → incident, task fails. |

Conditions (`when`): `{has: "compactor"}` or `{has: ["router","judge"]}` (node present and wired), `{tool: "search_docs"}`, `{setting: "model.tier", op: "==", value: "large"}` (also `"tool:<name>.<field>"`), `{toolQuality: "search_docs", op: ">=", value: 0.75}`, `{edge: ["retriever","model"]}`, `{state: "ready" | "first_turn" | "over_budget" | "lost_instructions" | "tool_error" | "tool_error_raw" | "tool_error_actionable" | "injected" | "repeating" | "judged_fail" | "compacted" | "resumed"}`, `{called: "read_file"}`, `{turn: ">=", value: 5}`, `{task: "t1"}`, `{tag: "refund"}`, and `{all: [...]}`, `{any: [...]}`, `{not: {...}}`. Ops: `== != > >= < <= in`.

Settings you can read (node `data`, defaults in `src/lab/nodes.ts`): model `tier` (small/medium/large), `temperature`, `reasoning`, `parallelTools`, `cachePrefix`, `systemPrompt`; loop `maxTurns`, `maxCost`; tool `name`, `description`, `errorRate`, `errorMode`, `idempotent`, `latencyMs`; memory `kind` (window/summary/vector/profile), `writePolicy` (always/validated/never); retriever `chunkSize`, `overlap`, `topK`; router `routes`; judge `passBar`, `maxRetries`; guardrail `rules`; approval `rule`; subagent `tier`; permissions `allow`/`ask`/`deny` (comma lists of tool names); compactor `trigger`, `strategy`; fallback `tier`. Text settings like `systemPrompt` can be matched with `{setting: "model.systemPrompt", op: "!=", value: ""}`; for "contains" logic use separate tool names or select fields instead.

`toolQuality` is a 0..1 rubric on the description (0.25 each): 40 to 400 characters; starts with a verb ("Searches", "Gets"); says when to use it ("Use this for...", "Do not use for..."); low word overlap with other tools' names and descriptions.

Metrics for goals: `success_rate`, `avg_turns`, `avg_cost`, `avg_tokens`, `avg_latency` (seconds), `incidents` (total), `incident_rate`, `approvals_per_task`, `stopped_rate`, `max_context`, `tool_accuracy` (share of tool calls that advanced a needed tool), `cost_per_success`.

Tuning loop: edit the JSON, run `npx vite-node scripts/sim.ts <id>`, repeat until the starter fails and the solution passes with margin, then `npx vitest run -t <id>`. Keep `runs` at the default 20 unless you need more stability (max 50). Write transcript `text` as realistic tool calls and answers, because learners read them.

## 3. Code labs: `src/content/codelabs/<id>/`

Four files. Reference: `codelabs/tools/`.

- `README.md` — frontmatter `title:` (and `realModel: false` if a real model makes no sense), then instructions in Markdown: `## The scenario`, `## Your task` (numbered steps), `## What the checks look for`.
- `starter.py` — runnable code with `# TODO` gaps. It must run without crashing where possible and fail at least one check.
- `solution.py` — the reference answer; passes every check.
- `check.py` — runs after the learner's code in the same namespace. Call `check("label", condition, "hint")`. Keep checks deterministic on the mock model.

Code uses only the standard library and `agentkit_mini` (`python/agentkit_mini/`): `MockModel`, `AnthropicModel`, `get_model(mock)` (returns the real model when the learner toggles it on), `Response`, `ToolCall`, `Usage`, `tool` decorator (`.schema`), `run_loop(model, tools, messages, system=, max_turns=, on_event=, pre_tool=, post_tool=)`, `count_tokens`, `count_context`, `cost(in, out, tier)`, `embed`, `cosine`, `VectorIndex`, `MCPServer`, `MCPClient`. Read the source before using it; it is short. Do not change `agentkit_mini`'s existing behaviour; if you need something new, ask the coordinator.

Code labs run in Pyodide in the browser, so no threads, no subprocess, no network (except the real-model toggle) and no packages beyond the stdlib. Verify with `python3 scripts/check_codelabs.py <id>`.

## 4. Capstone pages: `src/content/projects/<slug>/`

`index.mdx` (part 0: overview, architecture diagram, how to run) and one file per part `NN-name.mdx` with:

```yaml
---
title: "The loop"
project: "nanoharness"      # nanoharness | supportbot | deepresearch
part: 1                     # 0 = overview
tagline: "One line."
goal: "What you will have working at the end of this part."
lessons: ["agent_loop"]     # prerequisite lesson slugs
test: "pytest tests/test_part01_loop.py"
updated: 2026-10-09
---
```

Body: `## What you are building`, `## Steps` (numbered, each with a short code excerpt from the real project), `## Run the test`, `## What you just learned` (links back to lessons). The code lives in `projects/<slug>/` in this repo.
