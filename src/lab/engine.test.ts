import { describe, expect, it } from 'vitest';
import { simulate, runTask } from './engine';
import { GraphView, toolQuality } from './policy';
import { mulberry32 } from './prng';
import { SCENARIOS } from './scenarios';

describe('prng', () => {
  it('is deterministic', () => {
    const a = mulberry32(42), b = mulberry32(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
});

describe('engine', () => {
  const scn = SCENARIOS.agent_loop;
  it('same seed gives the same event log', () => {
    const g = new GraphView(scn.solution);
    const x = runTask(scn, g, scn.tasks[0], 1, 123);
    const y = runTask(scn, g, scn.tasks[0], 1, 123);
    expect(x).toEqual(y);
  });
  it('a lone model with a tool but no loop cannot finish', () => {
    const graph = {
      nodes: [
        { id: 'u', type: 'user' as const, data: {} },
        { id: 'm', type: 'model' as const, data: {} },
        { id: 't', type: 'tool' as const, data: { name: 'read_file' } },
      ],
      edges: [{ source: 'u', target: 'm' }, { source: 'm', target: 't' }],
    };
    expect(simulate(scn, graph).metrics.success_rate).toBeLessThan(0.3);
  });
  it('scores tool descriptions', () => {
    const g = new GraphView({ nodes: [
      { id: 'a', type: 'tool', data: { name: 'search_docs', description: 'Searches the product help center by keyword. Use this for questions about how a feature works.' } },
      { id: 'b', type: 'tool', data: { name: 'search', description: 'search' } },
    ], edges: [{ source: 'a', target: 'b' }] });
    expect(toolQuality(g.nodes[0], g.nodes)).toBe(1);
    expect(toolQuality(g.nodes[1], g.nodes)).toBeLessThanOrEqual(0.5);
  });
});

describe('every scenario', () => {
  for (const [id, scn] of Object.entries(SCENARIOS)) {
    it(`${id}: starter fails a goal, solution passes all`, () => {
      const starter = simulate(scn, scn.starter);
      const solution = simulate(scn, scn.solution);
      const failing = solution.goals.filter((x) => !x.pass).map((x) => `${x.label} (got ${x.actual.toFixed(3)})`);
      expect(failing, `solution fails: ${failing.join(', ')}`).toEqual([]);
      expect(starter.passed, `starter already passes: ${JSON.stringify(starter.metrics)}`).toBe(false);
    });
    it(`${id}: actions referenced by the policy exist`, () => {
      const keys = new Set(Object.keys(scn.actions));
      const used = [scn.policy.base, ...scn.policy.modifiers.flatMap((m) => [m.set ?? {}, m.shift ?? {}, m.scale ?? {}])].flatMap(Object.keys);
      expect(used.filter((k) => !keys.has(k))).toEqual([]);
      for (const n of [...scn.starter.nodes, ...scn.solution.nodes]) expect(scn.palette.includes(n.type) || n.type === 'user', `${n.type} not in palette`).toBe(true);
    });
  }
});
