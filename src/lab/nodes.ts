import type { NodeType } from './types';

export type FieldKind = 'select' | 'number' | 'text' | 'textarea' | 'bool' | 'range';

export interface FieldDef {
  key: string;
  label: string;
  kind: FieldKind;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  help?: string;
}

export interface NodeDef {
  type: NodeType;
  label: string;
  icon: string;
  blurb: string;
  defaults: Record<string, any>;
  fields: FieldDef[];
}

export const NODE_DEFS: Record<NodeType, NodeDef> = {
  user: {
    type: 'user', label: 'User', icon: '👤', blurb: 'Sends the scenario tasks into the graph.',
    defaults: {}, fields: [],
  },
  model: {
    type: 'model', label: 'Model', icon: '🧠', blurb: 'The LLM. Picks the next action each turn.',
    defaults: { tier: 'medium', temperature: 0.7, reasoning: false, parallelTools: false, cachePrefix: false, systemPrompt: '' },
    fields: [
      { key: 'tier', label: 'Tier', kind: 'select', options: ['small', 'medium', 'large'], help: 'Bigger is smarter, slower and pricier.' },
      { key: 'temperature', label: 'Temperature', kind: 'range', min: 0, max: 1, step: 0.1 },
      { key: 'reasoning', label: 'Reason before acting', kind: 'bool' },
      { key: 'parallelTools', label: 'Parallel tool calls', kind: 'bool' },
      { key: 'cachePrefix', label: 'Cache stable prefix', kind: 'bool', help: 'Bills the system prompt and tool schemas at 10% after the first call.' },
      { key: 'systemPrompt', label: 'System prompt', kind: 'textarea' },
    ],
  },
  loop: {
    type: 'loop', label: 'Agent loop', icon: '🔁', blurb: 'Feeds tool results back to the model until it is done.',
    defaults: { maxTurns: 60, maxCost: 0 },
    fields: [
      { key: 'maxTurns', label: 'Max turns', kind: 'number', min: 1, max: 500, help: '60 or more means no real cap.' },
      { key: 'maxCost', label: 'Max $ per task (0 = none)', kind: 'number', min: 0, max: 100, step: 0.05 },
    ],
  },
  tool: {
    type: 'tool', label: 'Tool', icon: '🔧', blurb: 'A function the model can ask your code to run.',
    defaults: { name: 'tool', description: '', errorRate: 0, errorMode: 'raw', latencyMs: 300, idempotent: false },
    fields: [
      { key: 'name', label: 'Name', kind: 'text' },
      { key: 'description', label: 'Description', kind: 'textarea', help: 'Say what it does, on what, and when to use it.' },
      { key: 'errorMode', label: 'Error messages', kind: 'select', options: ['raw', 'actionable'] },
      { key: 'idempotent', label: 'Idempotency key', kind: 'bool' },
      { key: 'latencyMs', label: 'Latency (ms)', kind: 'number', min: 0, max: 20000 },
    ],
  },
  memory: {
    type: 'memory', label: 'Memory', icon: '🗂️', blurb: 'What the agent keeps between turns and sessions.',
    defaults: { kind: 'window', writePolicy: 'always' },
    fields: [
      { key: 'kind', label: 'Kind', kind: 'select', options: ['window', 'summary', 'vector', 'profile'] },
      { key: 'writePolicy', label: 'Write policy', kind: 'select', options: ['always', 'validated', 'never'] },
    ],
  },
  retriever: {
    type: 'retriever', label: 'Retriever', icon: '📚', blurb: 'Finds documents and adds them to the context.',
    defaults: { chunkSize: 2000, overlap: 0, topK: 3 },
    fields: [
      { key: 'chunkSize', label: 'Chunk size (tokens)', kind: 'number', min: 50, max: 8000 },
      { key: 'overlap', label: 'Overlap (tokens)', kind: 'number', min: 0, max: 1000 },
      { key: 'topK', label: 'Top k', kind: 'number', min: 1, max: 50 },
    ],
  },
  router: {
    type: 'router', label: 'Router', icon: '🔀', blurb: 'Classifies the request and sends it to a specialist.',
    defaults: { routes: '' },
    fields: [{ key: 'routes', label: 'Routes (comma separated)', kind: 'text' }],
  },
  judge: {
    type: 'judge', label: 'Judge', icon: '⚖️', blurb: 'Grades the answer and sends it back if it falls short.',
    defaults: { passBar: 0.7, maxRetries: 2 },
    fields: [
      { key: 'passBar', label: 'Pass bar', kind: 'range', min: 0, max: 1, step: 0.05 },
      { key: 'maxRetries', label: 'Max retries', kind: 'number', min: 0, max: 10 },
    ],
  },
  guardrail: {
    type: 'guardrail', label: 'Guardrail', icon: '🛡️', blurb: 'Blocks or redacts content that matches its rules.',
    defaults: { rules: '' },
    fields: [{ key: 'rules', label: 'Rules (tags, comma separated; empty = all)', kind: 'text', help: 'e.g. pii, injection, exfiltration' }],
  },
  approval: {
    type: 'approval', label: 'Human approval', icon: '✋', blurb: 'Pauses irreversible actions until a person says yes.',
    defaults: { rule: 'irreversible' },
    fields: [{ key: 'rule', label: 'Ask when', kind: 'select', options: ['irreversible', 'all_tools'] }],
  },
  subagent: {
    type: 'subagent', label: 'Subagent', icon: '🧩', blurb: 'A fresh context for a side task. Returns a short summary.',
    defaults: { tier: 'small' },
    fields: [{ key: 'tier', label: 'Child tier', kind: 'select', options: ['small', 'medium', 'large'] }],
  },
  permissions: {
    type: 'permissions', label: 'Permissions', icon: '🔐', blurb: 'Allow, ask, or deny each tool.',
    defaults: { allow: '', ask: '', deny: '' },
    fields: [
      { key: 'allow', label: 'Allow (tool names)', kind: 'text' },
      { key: 'ask', label: 'Ask first', kind: 'text' },
      { key: 'deny', label: 'Deny', kind: 'text' },
    ],
  },
  compactor: {
    type: 'compactor', label: 'Compactor', icon: '🗜️', blurb: 'Shrinks the context before the window fills.',
    defaults: { trigger: 0.8, strategy: 'summarize' },
    fields: [
      { key: 'trigger', label: 'Trigger at % of window', kind: 'range', min: 0.3, max: 1, step: 0.05 },
      { key: 'strategy', label: 'Strategy', kind: 'select', options: ['truncate', 'summarize', 'offload'] },
    ],
  },
  fallback: {
    type: 'fallback', label: 'Fallback model', icon: '🛟', blurb: 'Takes over when the primary model errors.',
    defaults: { tier: 'medium' },
    fields: [{ key: 'tier', label: 'Tier', kind: 'select', options: ['small', 'medium', 'large'] }],
  },
};

/** Illustrative "sim prices" per million tokens, and seconds per model call. */
export const TIERS: Record<string, { in: number; out: number; latency: number; window: number }> = {
  small: { in: 1, out: 5, latency: 0.8, window: 200000 },
  medium: { in: 3, out: 15, latency: 1.6, window: 200000 },
  large: { in: 15, out: 75, latency: 3.2, window: 200000 },
};
