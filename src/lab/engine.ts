import type { ActionDef, Graph, Metrics, Scenario, SimEvent, SimOutput, StateFlag, Task, TaskResult } from './types';
import { GraphView, applyModifiers, compare, list } from './policy';
import { mulberry32, pick } from './prng';
import { TIERS } from './nodes';

const PROMPT_TOKENS = 200;

/** Run one task once. Pure: same inputs, same events. */
export function runTask(scn: Scenario, g: GraphView, task: Task, run: number, seed: number): { events: SimEvent[]; result: TaskResult } {
  const rand = mulberry32(seed);
  const events: SimEvent[] = [];
  const model = g.first('model');
  const tier = TIERS[model?.data.tier ?? 'medium'] ?? TIERS.medium;
  const loop = g.first('loop');
  const compactor = g.first('compactor');
  const memory = g.first('memory');
  const fallback = g.first('fallback');
  const judge = g.first('judge');
  const guardrail = g.first('guardrail');
  const approval = g.first('approval');
  const perms = g.first('permissions');
  const subagent = g.first('subagent');

  const window = scn.window ?? tier.window;
  const system = scn.systemTokens ?? 1200;
  const hardCap = scn.hardCap ?? 60;
  const maxTurns = loop ? Math.max(1, Math.min(Number(loop.data.maxTurns) || hardCap, hardCap)) : 1;
  const maxCost = loop ? Number(loop.data.maxCost) || 0 : 0;

  const flags = new Set<StateFlag>(['first_turn']);
  const done = new Set<string>();
  const needs = task.needs ?? [];
  const pending = new Set<string>(); // side effects that happened despite an error
  let ctx = system + PROMPT_TOKENS;
  let maxCtx = ctx;
  let tokens = 0;
  let cost = 0;
  let latency = 0;
  let turn = 0;
  let incidents = 0;
  let approvals = 0;
  let toolCalls = 0;
  let rightToolCalls = 0;
  let judgeRetries = 0;
  let outages = 0;
  let lastAction = '';
  let outcome: TaskResult['outcome'] | null = null;

  const ev = (kind: SimEvent['kind'], text: string, extra: Partial<SimEvent> = {}) =>
    events.push({ run, task: task.id, turn, kind, text, ctx: Math.round(ctx), cost, latency: Math.round(latency * 10) / 10, ...extra });

  const bill = (inTok: number, outTok: number, t = tier) => {
    let billedIn = inTok;
    if (model?.data.cachePrefix && turn > 1) billedIn = inTok - system * 0.9;
    tokens += inTok;
    cost += (billedIn * t.in + outTok * t.out) / 1e6;
  };

  const addContext = (n: number, nodeId?: string) => {
    ctx += n;
    const trig = compactor ? Number(compactor.data.trigger) : memory?.data.kind === 'summary' ? 0.9 : 0;
    if (trig && ctx > trig * window) {
      const strategy = compactor ? compactor.data.strategy : 'summarize';
      const before = Math.round(ctx);
      if (strategy === 'truncate') {
        ctx = Math.max(system + PROMPT_TOKENS, trig * window * 0.6);
        flags.add('lost_instructions');
        ev('compact', `Truncated oldest messages: ${before} → ${Math.round(ctx)} tokens. The original task was dropped.`, { nodeId: compactor?.id, bad: true });
      } else if (strategy === 'offload') {
        ctx = system + PROMPT_TOKENS + (ctx - system) * 0.15;
        latency += 0.5;
        ev('compact', `Offloaded old tool results to files: ${before} → ${Math.round(ctx)} tokens.`, { nodeId: compactor?.id });
      } else {
        bill(ctx, 800, TIERS.small);
        latency += 1.5;
        ctx = system + PROMPT_TOKENS + 800 + (ctx - system) * 0.1;
        ev('compact', `Summarized history: ${before} → ${Math.round(ctx)} tokens.`, { nodeId: compactor?.id ?? memory?.id });
      }
      flags.add('compacted');
    }
    if (ctx > window) {
      ev('system', `Context ${Math.round(ctx)} / ${window} tokens. The oldest messages fell out of the window, including the task.`, { bad: true, nodeId: nodeId ?? model?.id });
      ctx = window;
      flags.add('over_budget');
      flags.add('lost_instructions');
    }
    maxCtx = Math.max(maxCtx, ctx);
  };

  /** Interceptors for risky actions. Returns true when something stopped it. */
  const intercept = (def: ActionDef, key: string): boolean => {
    const tool = def.tool;
    if (perms && tool && list(perms.data.deny).includes(tool)) {
      ev('blocked', `Permissions denied ${tool}.`, { nodeId: perms.id });
      return true;
    }
    if (perms && tool && list(perms.data.ask).includes(tool)) {
      approvals++;
      ev('approval', `Asked the user before ${tool}. ${def.legit ? 'Approved.' : 'Denied.'}`, { nodeId: perms.id });
      return !def.legit;
    }
    if (guardrail && def.guardTag) {
      const rules = list(guardrail.data.rules);
      if ((rules.length === 0 || rules.includes(def.guardTag)) && rand() < 0.97) {
        ev('blocked', `Guardrail caught ${def.guardTag}: "${def.text}"`, { nodeId: guardrail.id });
        return true;
      }
    }
    if (approval && (def.irreversible || def.kind === 'dangerous' || def.kind === 'injection' || approval.data.rule === 'all_tools')) {
      approvals++;
      ev('approval', `Paused for a human: "${def.text}". ${def.legit ? 'Approved.' : 'Denied.'}`, { nodeId: approval.id });
      return !def.legit;
    }
    void key;
    return false;
  };

  ev('user', task.prompt);

  while (outcome === null) {
    turn++;
    if (turn > 1) flags.delete('first_turn');

    // Primary model outage.
    if (scn.outageRate && rand() < scn.outageRate) {
      if (fallback) {
        const ft = TIERS[fallback.data.tier] ?? TIERS.medium;
        latency += 2 + ft.latency;
        ev('system', `Primary model returned 529 (overloaded). Retried on the ${fallback.data.tier} fallback.`, { nodeId: fallback.id });
      } else {
        outages++;
        latency += 30;
        ev('system', `Primary model returned 529 (overloaded). No fallback; waited 30s.`, { bad: true, nodeId: model?.id });
        if (outages >= 3) { outcome = 'outage'; break; }
        if (turn >= maxTurns) { outcome = 'stopped'; break; }
        continue;
      }
    }

    const weights = applyModifiers(scn.policy.base, scn.policy.modifiers, g, { flags, turn, task, done });
    for (const [k, def] of Object.entries(scn.actions)) {
      if (!(k in weights)) continue;
      if (def.tool && def.kind === 'tool' && !g.tool(def.tool)) weights[k] = 0;
      if (def.kind === 'tool' && def.tool && done.has(def.tool) && needs.includes(def.tool)) weights[k] *= 0.2;
      if (def.kind === 'repeat' && !lastAction) weights[k] = 0;
    }
    const key = pick(weights, rand);
    if (!key) { ev('system', 'The model had no available action.', { bad: true }); outcome = 'stopped'; break; }
    const def = scn.actions[key];
    if (!def) throw new Error(`Scenario ${scn.id}: unknown action ${key}`);

    flags.delete('judged_fail');
    const inTok = ctx;
    const outTok = def.outputTokens ?? 150;
    bill(inTok, outTok);
    latency += tier.latency + (def.latencyMs ?? 0) / 1000;
    let add = task.tokensPerTurn ?? def.tokens ?? 300;
    if (def.offloadable && subagent) {
      add = Math.round(add * 0.15);
      const st = TIERS[subagent.data.tier] ?? TIERS.small;
      cost += ((def.tokens ?? 300) * st.in) / 1e6;
      ev('model', `Delegated to a subagent: ${def.text} (returned a ${add}-token summary)`, { nodeId: subagent.id });
    }

    const repeating = key === lastAction;
    if (repeating) flags.add('repeating'); else flags.delete('repeating');
    lastAction = key;

    switch (def.kind) {
      case 'think':
        addContext(add);
        ev('model', def.text, { nodeId: model?.id });
        break;

      case 'repeat':
        addContext(add);
        ev('model', def.text, { nodeId: model?.id, bad: true });
        break;

      case 'tool': {
        const toolNode = def.tool ? g.tool(def.tool) : undefined;
        if (!loop) {
          ev('model', `Requested ${def.text}, but nothing runs the tool and feeds the result back.`, { nodeId: model?.id, bad: true });
          outcome = 'stopped';
          break;
        }
        if (!def.offloadable || !subagent) ev('model', `→ ${def.text}`, { nodeId: model?.id });
        toolCalls++;
        if (def.tool && needs.includes(def.tool) && !done.has(def.tool)) rightToolCalls++;
        if (intercept({ ...def, legit: def.legit ?? true }, key)) {
          addContext(80);
          break;
        }
        const n = def.batch ?? 1;
        const tLat = Number(toolNode?.data.latencyMs ?? 300) / 1000;
        if (n > 1 && !model?.data.parallelTools) {
          latency += n * (tLat + tier.latency);
          turn += n - 1;
          for (let i = 1; i < n; i++) bill(ctx + i * (add / n), outTok);
        } else {
          latency += tLat;
        }
        const errRate = Number(toolNode?.data.errorRate ?? 0);
        if (errRate > 0 && rand() < errRate) {
          const actionable = toolNode?.data.errorMode === 'actionable';
          flags.add('tool_error');
          flags.delete(actionable ? 'tool_error_raw' : 'tool_error_actionable');
          flags.add(actionable ? 'tool_error_actionable' : 'tool_error_raw');
          if (def.sideEffect && rand() < 0.5) pending.add(def.tool!);
          addContext(actionable ? 120 : 900);
          ev('tool_error', actionable
            ? `${def.tool} failed: "Timed out after 10s. Safe to retry; try again."`
            : `${def.tool} failed: Traceback (most recent call last): ... ConnectionResetError [Errno 104]`, { nodeId: toolNode?.id, bad: !actionable });
          break;
        }
        flags.delete('tool_error'); flags.delete('tool_error_raw'); flags.delete('tool_error_actionable');
        if (def.sideEffect && def.tool && pending.has(def.tool)) {
          pending.delete(def.tool);
          if (!toolNode?.data.idempotent) {
            incidents++;
            ev('incident', `Duplicate side effect: ${def.tool} ran twice (the first "failed" call had already gone through).`, { nodeId: toolNode?.id, bad: true });
          } else {
            ev('tool', `${def.tool}: idempotency key matched the first call; no duplicate.`, { nodeId: toolNode?.id });
          }
        }
        if (def.tool) done.add(def.tool);
        if (def.untrusted) flags.add('injected');
        addContext(add, toolNode?.id);
        ev('tool', `${def.tool ?? 'tool'} returned ${add} tokens${def.untrusted ? ' (untrusted content)' : ''}.`, { nodeId: toolNode?.id });
        break;
      }

      case 'dangerous':
      case 'injection': {
        ev('model', `→ ${def.text}`, { nodeId: model?.id, bad: true });
        if (intercept(def, key)) { addContext(80); break; }
        incidents++;
        ev('incident', def.incident ?? `Incident: ${def.text}`, { bad: true, nodeId: model?.id });
        outcome = 'incident';
        break;
      }

      case 'answer': {
        if (def.incident) {
          if (intercept({ ...def, legit: false }, key)) { addContext(80); break; }
          ev('model', def.text, { nodeId: model?.id, bad: true });
          incidents++;
          ev('incident', def.incident, { bad: true, nodeId: model?.id });
          outcome = 'incident';
          break;
        }
        ev('model', def.text, { nodeId: model?.id, bad: !def.correct });
        if (judge) {
          const bar = Number(judge.data.passBar);
          bill(ctx, 200, TIERS.small);
          latency += TIERS.small.latency;
          const reject = def.correct ? rand() < Math.max(0, bar - 0.85) * 3 : rand() < 0.25 + 0.7 * bar;
          if (reject && judgeRetries < Number(judge.data.maxRetries)) {
            judgeRetries++;
            flags.add('judged_fail');
            addContext(250);
            ev('judge', `Judge: below the bar (${bar}). Sent back with feedback.`, { nodeId: judge.id });
            break;
          }
          ev('judge', `Judge: ${reject ? 'retries used up, passing it through' : 'passes'}.`, { nodeId: judge.id });
        }
        outcome = def.correct ? 'correct' : 'wrong';
        break;
      }
    }

    if (needs.length && needs.every((t) => done.has(t))) flags.add('ready');
    if (outcome) break;
    if (maxCost && cost > maxCost) {
      ev('system', `Budget cap hit: $${cost.toFixed(3)} > $${maxCost}. Stopped gracefully and reported progress.`, { nodeId: loop?.id });
      outcome = 'stopped';
      break;
    }
    if (turn >= maxTurns) {
      if (loop && maxTurns >= hardCap) {
        incidents++;
        ev('incident', `Runaway: ${turn} turns with no stop condition. Killed by the platform.`, { bad: true, nodeId: loop.id });
        outcome = 'runaway';
      } else {
        ev('system', loop ? `Max turns (${maxTurns}) reached. Stopped.` : 'One call, no loop: the run ends here.', { nodeId: loop?.id ?? model?.id, bad: !loop });
        outcome = 'stopped';
      }
    }
  }

  const success = outcome === 'correct';
  ev('result', success ? 'Task succeeded.' : `Task failed: ${outcome}.`, { bad: !success });
  return {
    events,
    result: {
      run, task: task.id, success, outcome: outcome!, turns: turn, tokens, cost, latency,
      incidents, approvals, maxContext: maxCtx, toolCalls, rightToolCalls,
    },
  };
}

export function metricsOf(results: TaskResult[]): Metrics {
  const n = results.length || 1;
  const sum = (f: (r: TaskResult) => number) => results.reduce((s, r) => s + f(r), 0);
  const succ = sum((r) => (r.success ? 1 : 0));
  const calls = sum((r) => r.toolCalls);
  return {
    success_rate: succ / n,
    avg_turns: sum((r) => r.turns) / n,
    avg_cost: sum((r) => r.cost) / n,
    avg_tokens: sum((r) => r.tokens) / n,
    avg_latency: sum((r) => r.latency) / n,
    incidents: sum((r) => r.incidents),
    incident_rate: sum((r) => r.incidents) / n,
    approvals_per_task: sum((r) => r.approvals) / n,
    stopped_rate: sum((r) => (r.outcome === 'stopped' ? 1 : 0)) / n,
    max_context: Math.max(0, ...results.map((r) => r.maxContext)),
    tool_accuracy: calls ? sum((r) => r.rightToolCalls) / calls : 1,
    cost_per_success: succ ? sum((r) => r.cost) / succ : Infinity,
  };
}

/** Run every task for seeds 1..runs. */
export function simulate(scn: Scenario, graph: Graph, runs = scn.runs ?? 20): SimOutput {
  const g = new GraphView(graph);
  const events: SimEvent[] = [];
  const results: TaskResult[] = [];
  for (let run = 1; run <= runs; run++) {
    scn.tasks.forEach((task, i) => {
      const out = runTask(scn, g, task, run, run * 1009 + i * 7919);
      if (run <= 3) events.push(...out.events);
      results.push(out.result);
    });
  }
  const metrics = metricsOf(results);
  const goals = scn.goals.map((goal) => ({
    id: goal.id, label: goal.label, actual: metrics[goal.metric], pass: compare(metrics[goal.metric], goal.op, goal.value),
  }));
  const hot = new Map<string, number>();
  for (const e of events) if (e.bad && e.nodeId) hot.set(e.nodeId, (hot.get(e.nodeId) ?? 0) + 1);
  return {
    events, results, metrics, goals,
    passed: goals.every((x) => x.pass),
    hotNodes: [...hot.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([id]) => id),
  };
}
