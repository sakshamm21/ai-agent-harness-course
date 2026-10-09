# Free Agent Harness: build plan

A free, static, hands-on course for learning AI agents and agent harnesses from zero to shipped projects, modeled on [freesystemdesign.com](https://freesystemdesign.com/).

This document is the full spec. The next agent should be able to build the site from it without asking questions. Every choice that the requester (Sak) didn't specify is marked **Default**. Change a default only if Sak asks.

---

## 1. What we are copying from freesystemdesign.com, and why it works

I studied the live site on 2026-10-09. Its structure:

| Element | How the reference does it | What we do |
|---|---|---|
| Promise | "Learn system design by building it." 46 lessons, free, no login for early lessons. | "Learn AI agents by building them." About 54 lessons, free, **no login anywhere** (Default). |
| Home page | One long page. 8 section headings, each with a count and a list of lesson links. Footer has About and Privacy. No sidebar. | Same layout. Sections listed in order with lesson counts. Local progress ticks next to each lesson. |
| URLs | Clean paths: `/c/<slug>/` for the lesson, `/c/<slug>/build/` for the hands-on page. | Same: `/c/<slug>/` and `/c/<slug>/build/`. Capstones live at `/p/<slug>/`. |
| Lesson page | Top nav: All concepts · previous · next. Title, one-line tagline, byline. 4 to 6 short H2 sections that tell a story: **problem → insight → solution → the math → the tradeoff**. Ends with "Now build it yourself" linking to the build page. Same nav repeated at the bottom. | Identical skeleton (see §5). Our "math" section is tokens, cost, latency or success rate. |
| Build page | Separate page. A concrete scenario with numbers ("150 r/s of reads, DB handles 30 r/s"). Drag components on a canvas, connect them, run a live traffic simulation that shows where the design breaks. | **Agent Lab**: drag agent parts (model, tools, memory, guardrail, router, judge) onto a canvas, wire them, run a scripted scenario through a deterministic simulated model, and watch where it fails (loops, context overflow, wrong tool, injection, cost blowup). See §6. |
| Interview section | A 6-step method, then worked designs (URL shortener, news feed, YouTube), each walked through the method and then built. | **Case studies** walked through a 6-step agent design method, then **capstone projects** you build end to end in real code. |
| Tone | Short sentences, second person, one idea per section, concrete numbers, ends on the tradeoff. | Same. Style guide in §5.3. |

The two things that make the reference work, and that we must not lose: **every concept has a hands-on page with a failure you can see**, and **every lesson ends on a tradeoff, not a conclusion**.

---

## 2. Decisions (defaults)

| Decision | Default | Why |
|---|---|---|
| Site name | **Free Agent Harness** (domain later; works on the free subdomain until then) | Mirrors the reference name. Sak can rename. |
| Static site generator | **Astro 5** with MDX content collections | Path-based static pages like the reference, zero JS by default, React islands only on build pages. |
| Interactive islands | **React 19 + React Flow (`@xyflow/react`)** for the canvas | React Flow is the standard for node-and-wire editors. |
| In-browser Python | **Pyodide** for code labs (lazy-loaded only on lab pages) | Learners run real Python agent code with no install. |
| Styling | Tailwind CSS 4, dark default theme (`#08090d` background like the reference), light theme toggle | Matches the reference look. |
| Search | Pagefind (static, built at deploy time) | Free, no server. |
| Progress | `localStorage` only, wrapped in try/catch | No accounts, no backend. |
| Host | **Cloudflare Pages** (free tier: unlimited bandwidth, custom domain, preview deploys per branch) | Best free static host for this. Fallback: GitHub Pages via Actions (same build output). |
| Repo | New public GitHub repo `free-agent-harness` under Sak's account (`sakshamm21`) | Needed for Cloudflare Pages Git integration. |
| Code labs language | **Python 3.12** (primary). TypeScript versions are out of scope for v1. | Most agent learning material and SDKs are Python first. |
| Model provider in labs | **Provider-agnostic interface, Anthropic Claude as the worked example** (`claude-sonnet-5-5` default, `claude-haiku-5-5` for cheap steps). Every lab also runs on a **mock model** so it works offline and free. | Learners without an API key can still finish every lab. |
| API keys | Never stored on any server. In-browser labs that call a real model take a key the user pastes; kept in `sessionStorage` only, sent directly to the provider. | No backend, no liability. |
| Analytics | Cloudflare Web Analytics (cookieless) | Free, no consent banner needed. |
| Licence | Content CC BY-NC-SA 4.0, code MIT | Common for free courses. |

---

## 3. Curriculum

Nine sections, 54 lessons, 3 capstones. Each lesson has a slug, a one-line tagline, a real-world example, and a build-page scenario. Build-page scenarios refer to the Agent Lab (§6) unless marked **[Code lab]**, which means a Pyodide Python exercise (§7).

### Section 1. Foundations (7): how a model behaves before it is an agent

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 1 | `llm` | What an LLM Actually Does | It predicts the next token. Everything else is built on that. | ChatGPT autocomplete feel; why it confidently invents citations | [Code lab] Call the mock model, watch token-by-token output, change temperature, see variance |
| 2 | `tokens` | Tokens and the Context Window | The model only knows what fits in the window. | Pasting a 300-page PDF and the model forgetting chapter 1 | Lab: feed a growing conversation into a 8k-token model until it truncates; read the token meter |
| 3 | `prompting` | System Prompts and Messages | Roles, instructions, and why order matters. | Support bot that ignores policy because it was buried in turn 40 | Lab: move one instruction between system and user, compare pass rate over 20 runs |
| 4 | `structured` | Structured Output | Getting JSON you can parse, every time. | Invoice extraction pipeline breaking on a stray sentence | [Code lab] Parse with and without schema-constrained output; count failures |
| 5 | `cost` | Cost and Latency Math | Price per million tokens times tokens per task times tasks per day. | A $40/day prototype that becomes $40k/month in production | Lab: given traffic and token counts, pick the model mix that fits a $500/month budget |
| 6 | `chat_vs_agent` | Chatbot vs Workflow vs Agent | Who decides the next step: you, your code, or the model? | FAQ bot vs Zapier-style LLM chain vs Claude Code | Lab: same task solved three ways; compare steps, cost, success |
| 7 | `when_not` | When Not to Build an Agent | Most problems want a single well-made call. | Teams replacing a 3-line regex with a $2 agent run | Lab: five tasks; mark which need an agent, then run them and check |

### Section 2. Tool Use (7): giving the model hands

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 8 | `tools` | Function Calling | The model asks; your code acts. | Weather and calendar assistants | [Code lab] Define a `get_weather` tool, handle the tool call, return the result |
| 9 | `agent_loop` | The Agent Loop | Call model, run tools, append results, repeat until done. | The core loop inside every coding agent | Lab: wire Model ↔ Tools ↔ Loop; run "find the bug in this file" |
| 10 | `react` | ReAct: Reason then Act | Thinking between tool calls makes fewer wrong moves. | Research assistants that plan their next search | Lab: toggle reasoning on/off; compare wrong-tool rate |
| 11 | `tool_design` | Designing Good Tools | Names, descriptions and errors are prompts too. | Ambiguous `search` vs `search_docs` causing wrong picks | Lab: rename and redescribe tools until tool-choice accuracy > 90% |
| 12 | `tool_errors` | Tool Errors and Recovery | Return errors the model can act on. | API returns 500 and the agent hallucinates success | Lab: inject failures; compare raw stack trace vs actionable error message |
| 13 | `parallel_tools` | Parallel Tool Calls | Independent calls in one turn cut latency. | Fetching 5 files at once instead of one per turn | Lab: same task sequential vs parallel; read the latency chart |
| 14 | `mcp` | Model Context Protocol (MCP) | One standard plug for tools, resources and prompts. | Connecting an agent to GitHub, Slack, a database through MCP servers | [Code lab] Write a tiny MCP-style server exposing two tools; connect the agent to it |

### Section 3. The Harness (9): the program around the model

This is the heart of the course. A harness is everything that is not the model: the loop, prompt assembly, tool runtime, context management, permissions, state, hooks and UI.

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 15 | `harness` | What Is an Agent Harness | Same model, different harness, very different agent. | Claude Code, Cursor agent, Codex CLI, OpenHands share models but behave differently | Lab: swap harness presets around one fixed model; compare success on 10 tasks |
| 16 | `prompt_assembly` | Assembling the Context | System prompt + tool schemas + memory + history + the new message. | How coding agents inject repo instructions files (CLAUDE.md, AGENTS.md) | Lab: build the context stack block by block; watch token budget |
| 17 | `context_mgmt` | Context Management and Compaction | Summarize, trim, or offload before the window fills. | Long coding sessions that auto-compact | Lab: 200-turn task; pick truncate vs summarize vs file offload; see which still finishes |
| 18 | `stop_conditions` | Stop Conditions and Budgets | Max turns, max tokens, max dollars, done signals. | Runaway agent loops burning a weekend of credits | Lab: agent stuck in a loop; add turn and cost caps; see graceful stop |
| 19 | `permissions` | Permissions and Sandboxing | Decide what runs without asking, what asks, and what never runs. | Allow-lists for shell commands; containerized execution | Lab: classify 12 tool calls into allow / ask / deny; run a scenario with `rm -rf` bait |
| 20 | `hooks` | Hooks and Lifecycle Events | Run your code before and after every tool call. | Auto-format after edit; block writes to `.env` | [Code lab] Add pre-tool and post-tool hooks to the mini harness |
| 21 | `sessions` | Sessions, State and Resume | Persist the transcript so work survives a crash. | Resuming a coding session the next day | Lab: kill the run mid-task; resume from saved state vs restart |
| 22 | `streaming` | Streaming and UX | Show progress as it happens; let users interrupt. | Token streaming and live tool status in chat UIs | [Code lab] Stream events from the loop; render a live status line |
| 23 | `subagents` | Subagents | Spawn a fresh context for a side task, get a summary back. | A coding agent delegating "search the codebase" to a subagent | Lab: main agent context overflows; add a subagent node; context stays small |

### Section 4. Memory and Retrieval (6)

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 24 | `memory_types` | Kinds of Memory | Working, episodic, semantic, procedural. | Assistants that remember your preferences across chats | Lab: same user over 3 sessions with and without long-term memory |
| 25 | `embeddings` | Embeddings and Similarity | Text to vectors; nearby means related. | Semantic search over support tickets | [Code lab] Embed 50 FAQs with a tiny bundled model; query by meaning |
| 26 | `rag` | Retrieval-Augmented Generation | Look it up, then answer, with citations. | Docs chatbots; legal research tools | Lab: wire Retriever → Model; measure answer accuracy and citation rate |
| 27 | `chunking` | Chunking and Indexing | Chunk size decides what the model can find. | Policy answers cut mid-sentence | Lab: vary chunk size and overlap; read the recall chart |
| 28 | `agentic_search` | Agentic Search vs RAG | Let the agent grep, open files and follow links itself. | Coding agents that search with grep instead of a vector DB | Lab: same codebase question via RAG vs agentic search; compare accuracy and cost |
| 29 | `memory_write` | Writing Memory Safely | What to save, when, and how to forget. | Memory poisoned by one bad session | Lab: add a memory-write policy; replay a poisoning attempt |

### Section 5. Patterns and Multi-Agent (7)

Follows the workflow and agent patterns from Anthropic's "Building effective agents" (Dec 2024), plus handoffs.

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 30 | `chaining` | Prompt Chaining | Break the job into fixed steps with checks between them. | Generate outline → check → write marketing copy | Lab: one big prompt vs a 3-step chain with a gate |
| 31 | `routing` | Routing | Classify first, then send to the right specialist. | Support triage: refunds vs tech vs sales | Lab: add a Router node; per-route accuracy |
| 32 | `parallelization` | Parallelization and Voting | Run in parallel, then combine or vote. | Code review by several reviewers; content moderation votes | Lab: 1 vs 3 voters; accuracy vs cost curve |
| 33 | `orchestrator` | Orchestrator–Workers | A lead agent plans and hands out subtasks. | Multi-agent deep research systems | Lab: orchestrator splits a research question across 4 workers |
| 34 | `evaluator_optimizer` | Evaluator–Optimizer | One drafts, one critiques, loop until good. | Translation and code refinement loops | Lab: add a Judge node with a pass bar; watch quality and cost rise |
| 35 | `planning` | Planning and Replanning | Write a plan, track it, change it when reality disagrees. | Todo lists in coding agents | Lab: a tool fails mid-plan; compare static plan vs replanning |
| 36 | `handoffs` | Handoffs and Shared State | Pass control and context between agents cleanly. | Sales agent handing a customer to a support agent | Lab: handoff with full transcript vs summary; measure what gets lost |

### Section 6. Reliability and Safety (7)

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 37 | `guardrails` | Guardrails | Check inputs and outputs before they cause harm. | Blocking PII in outbound emails | Lab: add input and output guardrail nodes; replay 20 risky requests |
| 38 | `prompt_injection` | Prompt Injection | Data that tries to become instructions. | A web page telling a browsing agent to email your files | Lab: agent reads a poisoned page; add trust boundaries until the exfiltration fails |
| 39 | `hitl` | Human in the Loop | Ask before irreversible actions. | Approving refunds over $100; approving a deploy | Lab: place an Approval node; trade off approvals per task vs incidents |
| 40 | `idempotency` | Retries and Idempotent Tools | A retried tool call must not charge the card twice. | Duplicate orders from retried agent calls | Lab: flaky payment tool; add idempotency keys |
| 41 | `timeouts` | Timeouts, Fallbacks and Model Failover | When the model or a tool is slow or down. | Provider outage taking a product down | Lab: primary model returns 529s; add fallback model |
| 42 | `determinism` | Taming Nondeterminism | Same input, different run. Design for it. | Flaky agent tests in CI | Lab: run a task 50 times; read the success distribution; reduce variance |
| 43 | `computer_use` | Browser and Computer-Use Agents | Screens are tools too, and slower and riskier ones. | Agents that fill web forms and book things | Lab: browser-agent scenario with a fake site; add confirmations on submit |

### Section 7. Evals and Operating Agents (6)

| # | Slug | Title | Tagline | Real-world example | Build scenario |
|---|---|---|---|---|---|
| 44 | `evals` | Why Evals Come First | If you can't measure it, every prompt change is a guess. | Teams shipping regressions on prompt tweaks | [Code lab] Write a 20-case eval set for the support agent; score it |
| 45 | `llm_judge` | LLM-as-Judge | Use a model to grade, then check the grader. | Grading open-ended answers at scale | Lab: judge vs human labels; compute agreement |
| 46 | `trajectory_evals` | Trajectory and Tool-Use Evals | Grade the path, not just the answer. | SWE-bench-style task suites; tau-bench-style customer tasks | Lab: two agents with the same answer, one with a dangerous path; catch it |
| 47 | `tracing` | Tracing and Observability | Every model call and tool call, as a timeline. | Debugging why an agent took 40 turns | Lab: open a trace view; find the turn where it went wrong |
| 48 | `caching` | Prompt Caching and Cost Control | Reuse the stable prefix; pay less, answer faster. | Long system prompts cached across calls | Lab: reorder context so the stable part is first; read cost savings |
| 49 | `deploy` | Deploying an Agent | Queues, workers, secrets, versioned prompts. | Running agents as background jobs | Lab: architecture canvas (reuses system-design ideas): API → queue → agent workers → store |

### Section 8. Case Studies (5): the agent design method on real systems

Each follows the **6-step agent design method** (lesson 50) and ends with "Now build it yourself" linking to a simplified Lab scenario of that system. All case studies are written from public information only and say so.

| # | Slug | Title | What it teaches |
|---|---|---|---|
| 50 | `method` | How to Design an Agent (6-step method) | 1. Scope the job and the failure cost. 2. Napkin math (tasks/day, turns/task, tokens/turn, $). 3. Tools and permissions. 4. Loop and context strategy. 5. Evals and guardrails. 6. Tradeoffs, then build it. |
| 51 | `case_coding_agent` | Design a Coding Agent (like Claude Code) | Harness, file tools, bash sandbox, compaction, subagents, permissions |
| 52 | `case_support_agent` | Design a Customer Support Agent (like Intercom Fin) | RAG over help center, routing, escalation to humans, refund approval |
| 53 | `case_research_agent` | Design a Deep Research Agent | Orchestrator–workers, web search, citation checking, cost caps |
| 54 | `case_browser_agent` | Design a Browser Agent | Computer use, injection defence, confirmations |

### Section 9. Capstone Projects (3): real code, end to end

Capstones are not Lab scenarios. They are guided multi-part projects in a **companion repo** (`free-agent-harness-projects`), with each part's page on the site at `/p/<slug>/<part>/`. Every part has: goal, starter code link, step list, a test you run to pass, and "what you just learned". All run on the mock model by default and on a real API key optionally.

**Capstone 1 (flagship): Build Your Own Coding Agent Harness — `nanoharness`** (`/p/nanoharness/`)
A ~800-line Python CLI coding agent built from nothing.
1. The loop: model call, tool call, append, repeat (lesson 9).
2. Tools: `read_file`, `write_file`, `edit_file` (string replace), `list_dir`, `grep`, `bash`.
3. Permissions: allow / ask / deny rules, a y/n prompt in the terminal (lesson 19).
4. Sandbox: run `bash` inside a temp working dir with a timeout; optional Docker mode.
5. Context: token counting, automatic compaction by summarization at 70% of the window (lesson 17).
6. Project instructions: load `AGENTS.md` from the working dir into the system prompt (lesson 16).
7. Hooks: `pre_tool` / `post_tool` from a config file (lesson 20).
8. Sessions: save the transcript as JSONL; `--resume` (lesson 21).
9. Subagents: a `task` tool that runs a child loop with a fresh context and returns a summary (lesson 23).
10. Evals: 15 small bug-fix tasks with pytest checks; report pass rate, turns, tokens, cost (lessons 44 to 46).
Pass bar: ≥ 10/15 tasks with the real model; all tests of the harness itself pass with the mock model.

**Capstone 2: Customer Support Agent with RAG and Escalation — `supportbot`** (`/p/supportbot/`)
1. Ingest a bundled fake help center (60 articles, Markdown) into a local vector index (numpy, no external DB).
2. RAG answer with citations.
3. Tools: `lookup_order`, `issue_refund` (fake backend in SQLite), `escalate_to_human`.
4. Router: refund / order status / product question / other.
5. Guardrails: PII redaction on output; refund > $100 requires human approval.
6. Injection test: a poisoned help-article tries to trigger refunds.
7. Eval set of 40 conversations; LLM-as-judge plus exact checks on tool calls.
8. Simple web UI (FastAPI + a single HTML page) and a trace viewer.

**Capstone 3: Multi-Agent Research Assistant — `deepresearch`** (`/p/deepresearch/`)
1. Orchestrator that plans sub-questions.
2. Worker agents with a `search` tool (bundled offline corpus by default; optional real search API) and `fetch_page`.
3. Parallel workers with a cost cap.
4. Citation verifier agent (evaluator–optimizer).
5. Final report writer producing Markdown with sources.
6. Evals: 10 questions with reference facts; measure fact recall and citation precision.

Capstone pages carry a "Prerequisites" box listing the lessons they draw on, and every lesson links forward to the capstone part that uses it ("You'll build this in nanoharness part 5").

---

## 4. Site map and routes

```
/                         Home: hero + 9 sections with lesson lists + progress
/c/<slug>/                Lesson page
/c/<slug>/build/          Build page (Agent Lab or Code Lab)
/p/                       Projects index
/p/<slug>/                Capstone overview
/p/<slug>/<part>/         Capstone part
/glossary/                Glossary (auto-built from lesson frontmatter `terms`)
/about/                   About the course and author
/privacy/                 Privacy (localStorage only, cookieless analytics)
/404                      Not found
/sitemap-index.xml, /rss.xml, /og/<slug>.png (build-time generated OG images)
```

Home page order, top to bottom: hero ("Learn AI agents by building them." + "54 lessons. Free. No login.") → "Start here" button to `/c/llm/` → nine section blocks (heading, count, numbered lesson links with ✓ when complete) → Projects block (3 cards) → footer (About, Privacy, GitHub repo, licence).

---

## 5. Lesson page spec

### 5.1 Content format

One MDX file per lesson: `src/content/lessons/<slug>.mdx`.

```yaml
---
title: "Context Management and Compaction"
slug: "context_mgmt"
section: "harness"            # one of: foundations, tools, harness, memory, patterns, reliability, operate, cases
order: 17                     # global order, drives prev/next
tagline: "Summarize, trim, or offload before the window fills."
realWorld: "Long coding sessions that auto-compact"
build:
  type: "lab"                 # "lab" | "code" | "none"
  scenario: "context_mgmt"    # file in src/content/scenarios/
terms: ["context window", "compaction", "summarization"]
usedIn: ["nanoharness/5"]     # capstone parts that use this lesson
readingMinutes: 6
updated: 2026-10-09
---
```

Section metadata lives in `src/content/sections.json` (id, title, blurb, order).

### 5.2 Page skeleton (must match exactly)

1. Top nav: `All lessons` · `← <prev title>` · `<next title> →`
2. H1 title, tagline, byline ("by Sak" with a link to /about/), reading time
3. Body: **4 to 6 H2 sections in this arc**:
   1. **The problem** (a concrete failing situation with a number)
   2. **The insight** (why it fails)
   3. **The fix** (the mechanism, with one diagram)
   4. **Let us check the math** (tokens, $, latency or success rate worked through)
   5. **The tradeoff** (what the fix costs you; 2 to 3 mitigations)
   6. Optional **In the real world** (one named system and how it does this)
4. "Now build it yourself →" button to `/c/<slug>/build/`
5. "Used in: nanoharness part 5" chips (from `usedIn`)
6. 3-question quick check (multiple choice, answers revealed on click, no scoring stored) — an addition to the reference that helps retention
7. Bottom nav repeated; "Mark complete" toggle (localStorage)

Diagrams: inline SVG authored as Astro components in `src/components/diagrams/`, using theme CSS variables so they work in dark and light. No images of text.

### 5.3 Style guide (copy the reference's voice)

- Second person, present tense. Short sentences. One idea per H2.
- Open with a concrete scenario and a number in the first two sentences.
- Every lesson has a worked calculation.
- End on the tradeoff, never "and that's it".
- 600 to 1,000 words per lesson. Code snippets ≤ 20 lines; longer code goes in labs.
- Use real product names only for publicly documented behaviour; say "like" not "how X works internally" when inferring.
- No em-dashes in headings; no marketing adjectives.

### 5.4 Sample lesson outline (for calibration): `agent_loop`

- **H2 "You asked it to fix a bug. It answered with a guess."** One model call, no tools: it can't see the file, so 7 of 10 answers are wrong.
- **H2 "The model can't act, but it can ask."** Tool calls as requests.
- **H2 "Put a loop around it."** Pseudocode (12 lines): `while not done: resp = model(messages, tools); if resp.tool_calls: run them, append results; else: done`. Diagram of the cycle.
- **H2 "Let us check the math."** 6 turns × 3k input tokens growing to 18k → total input ~63k tokens per task; at $3/M input that's ~$0.19 per bug fix.
- **H2 "The tradeoff. Loops don't know when to stop."** Runaway turns, growing context, repeated tool calls → stop conditions (lesson 18), compaction (17), budgets.
- **H2 "In the real world."** Every coding agent (Claude Code, Codex CLI, OpenHands) runs a version of this loop.

---

## 6. Agent Lab (the build page engine)

The equivalent of the reference's drag-and-drop traffic simulator. It must run fully in the browser, free, deterministic, with no API key.

### 6.1 Layout

- Header: "Build: <lesson title>", the scenario brief (2 to 3 sentences with numbers), and goal checklist.
- Left: **palette** of nodes allowed in this scenario.
- Center: **canvas** (React Flow). Drag nodes, connect ports.
- Right: **inspector** for the selected node (e.g. model tier, temperature, max turns, tool description text, guardrail rules).
- Bottom: **Run** button, speed control, and three tabs: **Transcript** (messages and tool calls as chat bubbles), **Trace** (timeline of turns with tokens/latency/cost per step), **Metrics** (success rate, avg turns, tokens, $, incidents).
- Goal panel turns each goal green when met. When all are green: confetti-free "Passed" banner + "Next lesson →" and the lesson is marked complete.
- Links back: "← <lesson> lesson".

### 6.2 Node types

| Node | Inspector settings | Behaviour in sim |
|---|---|---|
| `user` | scenario-provided tasks | Emits tasks into the graph |
| `model` | tier (small / medium / large → price, latency, base skill), temperature, system prompt (textarea), reasoning on/off | Simulated policy (see 6.3) |
| `loop` | max turns, max $, stop-on-done | Runs model ↔ tools cycle |
| `tool` | name, description, error mode, latency, `idempotent` flag, `side_effect` level | Executes scripted results |
| `memory` | type (window / summary / vector), size | Changes what context the model sees |
| `retriever` | chunk size, top-k | Returns scripted documents with recall depending on settings |
| `router` | routes | Classifies with an accuracy that depends on model tier and route descriptions |
| `judge` | rubric, pass bar | Grades output; can loop back |
| `guardrail` | input/output, rules | Blocks or redacts matching content |
| `approval` | threshold rule | Pauses; simulated human approves/denies by script |
| `subagent` | child model tier | Fresh context; returns summary |
| `permissions` | allow / ask / deny lists | Gates tool calls |
| `compactor` | trigger % , strategy | Shrinks context |
| `fallback` | secondary model | Used when primary errors |

### 6.3 Simulation model (deterministic)

- A seeded PRNG (`mulberry32`) per run; "Run 50×" uses seeds 1..50, so results are reproducible and charts are stable.
- **Simulated model policy**: each scenario defines, per task, a small decision table: given visible context features (has needed tool? tool description quality score? relevant doc retrieved? context over budget? injected instruction present and untrusted?), the probability of each next action (`call_tool:X`, `answer_correct`, `answer_wrong`, `loop_repeat`, `follow_injection`). Model tier and reasoning flag shift those probabilities by scenario-defined deltas.
- Tool description quality is scored by a simple rubric (length bands, contains verb + object, mentions when to use, no overlap with another tool's keywords) so editing descriptions changes outcomes.
- Token accounting is real arithmetic: each message has a token count; context = sum; cost = tokens × tier price. Prices are illustrative and labelled so ("sim prices").
- Failures surface visually: the offending node pulses red, and the trace highlights the turn (e.g. "Turn 14: context 9,210 / 8,000 tokens, oldest messages dropped, task instructions lost").

### 6.4 Scenario file format

`src/content/scenarios/<id>.json`, validated with a Zod schema at build time:

```json
{
  "id": "context_mgmt",
  "brief": "This refactor takes about 200 turns. The model's window is 8,000 tokens and each turn adds ~300.",
  "palette": ["user", "model", "loop", "tool", "compactor", "memory"],
  "starter": { "nodes": [...], "edges": [...] },
  "tasks": [ { "id": "t1", "needs": ["read_file", "edit_file"], "turns": 200, "tokensPerTurn": 300 } ],
  "policy": { "base": {...}, "modifiers": [ { "when": "context_over_budget", "shift": { "answer_wrong": 0.4 } } ] },
  "goals": [
    { "id": "finish", "label": "Finish ≥ 90% of runs", "metric": "success_rate", "op": ">=", "value": 0.9 },
    { "id": "cost",   "label": "Average cost under $0.80", "metric": "avg_cost", "op": "<", "value": 0.8 }
  ],
  "hints": ["What happens to the first message when the window fills?", "Try a Compactor node at 70%."],
  "solution": { "nodes": [...], "edges": [...] }
}
```

Hints reveal one at a time; "Show solution" loads `solution` after 2 hints.

### 6.5 Engine code location

`src/lab/` as a framework-free TypeScript module (`engine.ts`, `policy.ts`, `tokens.ts`, `prng.ts`, `types.ts`) with **Vitest unit tests**, and `src/components/lab/` for the React UI. The engine must be pure (graph + scenario + seed → events), so it is testable and reusable by the capstone pages.

---

## 7. Code Lab (Pyodide)

For lessons marked [Code lab] and as a preview on capstone pages.

- Page shows: instructions, a CodeMirror 6 editor with starter code, **Run** and **Check** buttons, an output pane.
- Pyodide loads from jsDelivr on first click (pinned version), not on page load.
- A bundled Python package `agentkit_mini` (shipped as a wheel in `/public/py/`) provides:
  - `Model` interface with `MockModel` (scripted responses keyed by scenario) and `AnthropicModel` (calls the Messages API via `pyodide.http.pyfetch` with the user's pasted key; header `anthropic-dangerous-direct-browser-access: true`).
  - `tool` decorator that builds JSON schemas from type hints.
  - `run_loop(model, tools, messages, max_turns)`.
- **Check** runs hidden asserts from `src/content/codelabs/<slug>/check.py` and shows pass/fail per assert.
- "Use a real model" toggle: key input stored in `sessionStorage`, with a plain warning that it is sent straight to the provider from the browser.

---

## 8. Repository layout

```
free-agent-harness/
  astro.config.mjs
  package.json            # pnpm
  src/
    content/
      config.ts           # Zod schemas for lessons, scenarios, projects
      sections.json
      lessons/*.mdx       # 54 files
      scenarios/*.json
      codelabs/<slug>/{starter.py,check.py,README.md}
      projects/<slug>/*.mdx
    components/
      Nav.astro LessonLayout.astro QuickCheck.tsx ProgressTick.tsx ThemeToggle.tsx
      diagrams/*.astro
      lab/*.tsx           # Agent Lab UI
      codelab/*.tsx       # Pyodide UI
    lab/                  # pure TS engine + tests
    pages/
      index.astro
      c/[slug]/index.astro
      c/[slug]/build.astro
      p/index.astro  p/[slug]/index.astro  p/[slug]/[part].astro
      glossary.astro about.astro privacy.astro 404.astro
    styles/global.css
  public/py/agentkit_mini-*.whl
  python/agentkit_mini/   # source for the wheel + pytest
  .github/workflows/ci.yml
```

Companion repo `free-agent-harness-projects/` (Python, `uv`): `nanoharness/`, `supportbot/`, `deepresearch/`, each with `starter/` and `solution/` branches or folders, `tests/`, and a README mirroring the site pages. The mock model is shared via `agentkit_mini`.

---

## 9. Build milestones for the next agent

Ship in this order. Each milestone ends deployed to Cloudflare Pages preview.

**M0. Scaffold and deploy (day 1)**
- Ask Sak to create or allow creation of the GitHub repo, then scaffold Astro + Tailwind + MDX + React.
- Dark/light theme tokens, Nav, LessonLayout, home page reading `sections.json`.
- CI: `pnpm build`, `vitest`, link check (`lychee` or Astro's), Pagefind index.
- Connect Cloudflare Pages (build command `pnpm build`, output `dist`). Sak must click "Connect to Git" in their Cloudflare dashboard; the agent cannot do that step.
- Acceptance: the home page with all 9 sections and placeholder lesson stubs is live on `*.pages.dev`.

**M1. Lesson system + first 7 lessons**
- Content collections with Zod validation (build fails on bad frontmatter).
- Prev/next, progress ticks, quick check, glossary generation, OG images.
- Write Section 1 lessons fully to the §5 skeleton and style guide.
- Acceptance: Lighthouse ≥ 95 performance and accessibility on a lesson page; every lesson passes a frontmatter schema check.

**M2. Agent Lab engine + 3 scenarios**
- Pure engine with tests (seeded determinism test: same seed → identical event log).
- UI: palette, canvas, inspector, run, transcript/trace/metrics tabs, goals, hints, solution.
- Scenarios: `agent_loop`, `context_mgmt`, `prompt_injection`.
- Acceptance: each scenario's starter fails ≥ 1 goal and its `solution` passes all goals in a Vitest test; works at 375px width (palette becomes a bottom sheet).

**M3. Code Lab + `agentkit_mini`**
- Wheel built in CI from `python/agentkit_mini`, pytest green.
- Code labs for lessons 1, 4, 8, 14, 20, 22, 25, 44.
- Acceptance: each code lab's starter fails Check and the reference solution passes, verified by a Playwright test running Pyodide headless.

**M4. Remaining lessons and scenarios (Sections 2 to 7)**
- Write lessons 8 to 49 and their scenarios. Reuse node types; add new ones only if listed in §6.2.
- Acceptance: every lesson with `build.type: lab` has a scenario whose solution passes in tests.

**M5. Case studies (Section 8)**
- Lessons 50 to 54 with simplified Lab scenarios.

**M6. Capstones**
- Companion repo with `nanoharness` first (all 10 parts, mock-model tests green in CI), then `supportbot`, then `deepresearch`.
- Site pages `/p/...` for each part.
- Acceptance: `uv run pytest` green on mock model for every part's solution; README quickstart works from a clean clone.

**M7. Polish and launch**
- Pagefind search box, RSS, sitemap, 404, privacy page, About page.
- Custom domain on Cloudflare Pages if Sak buys one (optional; `*.pages.dev` is free).
- Acceptance: all links resolve; no console errors; mobile layout checked at 375px.

---

## 10. Quality bar and tests

- `pnpm build` fails on: invalid frontmatter, missing scenario file, broken internal link, scenario solution not passing.
- Vitest: engine determinism, policy modifiers, token math, every scenario's starter-fails / solution-passes.
- Playwright: home loads, a lesson's nav works, one lab passes when the solution is loaded, one code lab passes Check.
- Accessibility: keyboard can add nodes (palette items focusable, Enter adds to canvas center, arrow keys move, `C` connects to selected), all colours meet WCAG AA in both themes.
- Performance: lesson pages ship no JS except progress/quick-check islands (< 15 KB); lab JS loads only on `/build/` pages.

---

## 11. What the next agent needs from Sak

1. Permission to create the GitHub repo `free-agent-harness` (and `free-agent-harness-projects`) under `sakshamm21`, or the name of an existing repo to use.
2. Later, connecting the repo in their free Cloudflare account (one click flow); until then the agent can verify builds locally and in CI.
3. Optional: a byline name other than "Sak", and a custom domain.

Nothing else blocks the build. Everything above is decided.

---

## 12. Reference reading to cite inside lessons

Link these from the relevant lessons as "Further reading" (verify each URL resolves at build time):

- Anthropic, "Building effective agents" (workflow and agent patterns; Section 5)
- Anthropic engineering posts on Claude Code, the Claude Agent SDK, context engineering and multi-agent research (Sections 3, 5, 8)
- Model Context Protocol specification at modelcontextprotocol.io (lesson 14)
- Anthropic docs: tool use, prompt caching, computer use (lessons 8, 43, 48)
- ReAct paper (Yao et al., 2022) (lesson 10)
- SWE-bench and tau-bench papers (lesson 46)
- OWASP Top 10 for LLM Applications (lessons 37, 38)
- freesystemdesign.com as the format inspiration (About page credit)
