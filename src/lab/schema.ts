import { z } from 'zod';

const nodeType = z.enum(['user', 'model', 'loop', 'tool', 'memory', 'retriever', 'router', 'judge', 'guardrail', 'approval', 'subagent', 'permissions', 'compactor', 'fallback']);
const op = z.enum(['==', '!=', '>', '>=', '<', '<=', 'in']);
const graph = z.object({
  nodes: z.array(z.object({ id: z.string(), type: nodeType, data: z.record(z.any()).default({}), position: z.object({ x: z.number(), y: z.number() }).optional() })),
  edges: z.array(z.object({ id: z.string().optional(), source: z.string(), target: z.string() })),
});
const cond: z.ZodType<any> = z.lazy(() => z.union([
  z.object({ has: z.union([nodeType, z.array(nodeType)]) }).strict(),
  z.object({ tool: z.string() }).strict(),
  z.object({ setting: z.string(), op, value: z.any() }).strict(),
  z.object({ toolQuality: z.string(), op, value: z.number() }).strict(),
  z.object({ edge: z.tuple([nodeType, nodeType]) }).strict(),
  z.object({ state: z.enum(['ready', 'first_turn', 'over_budget', 'lost_instructions', 'tool_error', 'tool_error_raw', 'tool_error_actionable', 'injected', 'repeating', 'judged_fail', 'compacted', 'resumed']) }).strict(),
  z.object({ turn: op, value: z.number() }).strict(),
  z.object({ called: z.string() }).strict(),
  z.object({ task: z.string() }).strict(),
  z.object({ tag: z.string() }).strict(),
  z.object({ all: z.array(cond) }).strict(),
  z.object({ any: z.array(cond) }).strict(),
  z.object({ not: cond }).strict(),
]));
const metric = z.enum(['success_rate', 'avg_turns', 'avg_cost', 'avg_tokens', 'avg_latency', 'incidents', 'incident_rate', 'approvals_per_task', 'stopped_rate', 'max_context', 'tool_accuracy', 'cost_per_success']);

export const ScenarioSchema = z.object({
  id: z.string(),
  title: z.string(),
  brief: z.string(),
  palette: z.array(nodeType),
  starter: graph,
  solution: graph,
  runs: z.number().int().positive().optional(),
  window: z.number().positive().optional(),
  systemTokens: z.number().nonnegative().optional(),
  hardCap: z.number().int().positive().optional(),
  outageRate: z.number().min(0).max(1).optional(),
  tasks: z.array(z.object({
    id: z.string(), label: z.string(), prompt: z.string(),
    needs: z.array(z.string()).optional(), tokensPerTurn: z.number().optional(),
    tags: z.array(z.string()).optional(), weight: z.number().optional(),
  })).min(1),
  actions: z.record(z.object({
    kind: z.enum(['tool', 'answer', 'repeat', 'think', 'injection', 'dangerous']),
    text: z.string(),
    tool: z.string().optional(), correct: z.boolean().optional(),
    tokens: z.number().optional(), outputTokens: z.number().optional(), latencyMs: z.number().optional(),
    batch: z.number().int().positive().optional(), offloadable: z.boolean().optional(),
    untrusted: z.boolean().optional(), sideEffect: z.boolean().optional(),
    irreversible: z.boolean().optional(), legit: z.boolean().optional(),
    guardTag: z.string().optional(), incident: z.string().optional(),
  }).strict()),
  policy: z.object({
    base: z.record(z.number()),
    modifiers: z.array(z.object({
      when: cond, shift: z.record(z.number()).optional(), scale: z.record(z.number()).optional(),
      set: z.record(z.number()).optional(), note: z.string().optional(),
    }).strict()),
  }),
  goals: z.array(z.object({ id: z.string(), label: z.string(), metric, op, value: z.number() })).min(1),
  hints: z.array(z.string()).min(1),
  explain: z.string().optional(),
}).strict();
