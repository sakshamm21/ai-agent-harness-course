// Usage: npx vite-node scripts/sim.ts <scenario-id>   (prints starter vs solution metrics)
import { simulate } from '../src/lab/engine';
import { SCENARIOS } from '../src/lab/scenarios';
const ids = process.argv.slice(2);
for (const id of ids.length ? ids : Object.keys(SCENARIOS)) {
  const s = SCENARIOS[id];
  if (!s) { console.log('no scenario', id); continue; }
  for (const which of ['starter', 'solution'] as const) {
    const o = simulate(s, s[which]);
    const m = o.metrics;
    console.log(`${id.padEnd(22)} ${which.padEnd(8)} pass=${o.passed} success=${m.success_rate.toFixed(2)} turns=${m.avg_turns.toFixed(1)} cost=$${m.avg_cost.toFixed(4)} lat=${m.avg_latency.toFixed(1)}s inc=${m.incidents} appr=${m.approvals_per_task.toFixed(2)} maxctx=${m.max_context} toolacc=${m.tool_accuracy.toFixed(2)}  goals: ${o.goals.map((g) => (g.pass ? '✓' : '✗') + g.id + '=' + g.actual.toFixed(3)).join(' ')}`);
  }
}
