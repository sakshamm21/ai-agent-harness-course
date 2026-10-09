import type { Cond, Graph, LabNode, Modifier, NodeType, Op, StateFlag, Task } from './types';
import { NODE_DEFS } from './nodes';

/** Everything the engine needs to know about a wired graph, computed once per run. */
export class GraphView {
  readonly nodes: LabNode[];
  constructor(public graph: Graph) {
    const degree = new Map<string, number>();
    for (const e of graph.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    // A node counts only when it is wired into the graph (or is the only node).
    this.nodes = graph.nodes
      .filter((n) => graph.nodes.length === 1 || (degree.get(n.id) ?? 0) > 0)
      .map((n) => ({ ...n, data: { ...NODE_DEFS[n.type]?.defaults, ...n.data } }));
  }
  has(type: NodeType): boolean {
    return this.nodes.some((n) => n.type === type);
  }
  first(type: NodeType): LabNode | undefined {
    return this.nodes.find((n) => n.type === type);
  }
  tool(name: string): LabNode | undefined {
    return this.nodes.find((n) => n.type === 'tool' && String(n.data.name).trim() === name);
  }
  tools(): LabNode[] {
    return this.nodes.filter((n) => n.type === 'tool');
  }
  edge(a: NodeType, b: NodeType): boolean {
    const byId = new Map(this.nodes.map((n) => [n.id, n]));
    return this.graph.edges.some((e) => byId.get(e.source)?.type === a && byId.get(e.target)?.type === b);
  }
  /** "model.tier", "tool:search.errorMode", "loop.maxTurns" */
  setting(path: string): any {
    const dot = path.lastIndexOf('.');
    const head = path.slice(0, dot);
    const field = path.slice(dot + 1);
    const node = head.startsWith('tool:') ? this.tool(head.slice(5)) : this.first(head as NodeType);
    return node?.data[field];
  }
}

export function list(s: unknown): string[] {
  return String(s ?? '').split(',').map((x) => x.trim()).filter(Boolean);
}

export function compare(a: any, op: Op, b: any): boolean {
  if (a === undefined) return op === '!=';
  switch (op) {
    case '==': return a == b; // eslint-disable-line eqeqeq
    case '!=': return a != b; // eslint-disable-line eqeqeq
    case '>': return Number(a) > Number(b);
    case '>=': return Number(a) >= Number(b);
    case '<': return Number(a) < Number(b);
    case '<=': return Number(a) <= Number(b);
    case 'in': return Array.isArray(b) && b.map(String).includes(String(a));
  }
}

const STOP = new Set(['the', 'a', 'an', 'to', 'of', 'and', 'or', 'for', 'in', 'on', 'with', 'this', 'that', 'is', 'it', 'use', 'when', 'from', 'by', 'as', 'be']);
const words = (s: string) => new Set(s.toLowerCase().split(/[^a-z0-9_]+/).filter((w) => w.length > 2 && !STOP.has(w)));

/**
 * Tool description rubric, 0..1. Four checks worth 0.25 each:
 * length 40-400 chars, starts with a verb, says when to use it, and does not overlap another tool.
 */
export function toolQuality(tool: LabNode, all: LabNode[]): number {
  const d = String(tool.data.description ?? '').trim();
  const name = String(tool.data.name ?? '');
  let score = 0;
  if (d.length >= 40 && d.length <= 400) score += 0.25;
  const firstWord = d.split(/\s+/)[0]?.toLowerCase() ?? '';
  if (/^[a-z]+(s)?$/.test(firstWord) && (firstWord.endsWith('s') || VERBS.has(firstWord))) score += 0.25;
  if (/\b(use (this|it|when|for|only|to)|when |only for|do not use|don't use|instead of)\b/i.test(d)) score += 0.25;
  const mine = words(d + ' ' + name.replace(/_/g, ' '));
  const overlaps = all
    .filter((t) => t.id !== tool.id)
    .map((t) => {
      const theirs = words(String(t.data.description ?? '') + ' ' + String(t.data.name ?? '').replace(/_/g, ' '));
      const inter = [...mine].filter((w) => theirs.has(w)).length;
      const union = new Set([...mine, ...theirs]).size || 1;
      return inter / union;
    });
  if (d.length > 0 && Math.max(0, ...overlaps) < 0.3) score += 0.25;
  return score;
}

const VERBS = new Set(['get', 'find', 'search', 'read', 'write', 'edit', 'list', 'create', 'delete', 'update', 'send', 'fetch', 'look', 'lookup', 'run', 'check', 'return', 'issue', 'book', 'cancel', 'query', 'open', 'call', 'compute', 'convert', 'summarize', 'translate', 'add', 'remove', 'set', 'show', 'post', 'refund', 'escalate', 'grep', 'navigate', 'click', 'type', 'submit', 'retrieve', 'save', 'load', 'apply', 'execute']);

export interface CondState {
  flags: Set<StateFlag>;
  turn: number;
  task: Task;
  done?: Set<string>;
}

export function evalCond(c: Cond, g: GraphView, s: CondState): boolean {
  if ('all' in c) return c.all.every((x) => evalCond(x, g, s));
  if ('any' in c) return c.any.some((x) => evalCond(x, g, s));
  if ('not' in c) return !evalCond(c.not, g, s);
  if ('has' in c) return (Array.isArray(c.has) ? c.has : [c.has]).every((t) => g.has(t));
  if ('tool' in c) return !!g.tool(c.tool);
  if ('setting' in c) return compare(g.setting(c.setting), c.op, c.value);
  if ('toolQuality' in c) {
    const t = g.tool(c.toolQuality);
    return compare(t ? toolQuality(t, g.tools()) : undefined, c.op, c.value);
  }
  if ('edge' in c) return g.edge(c.edge[0], c.edge[1]);
  if ('state' in c) return s.flags.has(c.state);
  if ('turn' in c) return compare(s.turn, c.turn, c.value);
  if ('called' in c) return !!s.done?.has(c.called);
  if ('task' in c) return s.task.id === c.task;
  if ('tag' in c) return (s.task.tags ?? []).includes(c.tag);
  return false;
}

export function applyModifiers(base: Record<string, number>, mods: Modifier[], g: GraphView, s: CondState) {
  const w = { ...base };
  for (const m of mods) {
    if (!evalCond(m.when, g, s)) continue;
    for (const [k, v] of Object.entries(m.set ?? {})) w[k] = v;
    for (const [k, v] of Object.entries(m.shift ?? {})) w[k] = (w[k] ?? 0) + v;
    for (const [k, v] of Object.entries(m.scale ?? {})) w[k] = (w[k] ?? 0) * v;
  }
  for (const k of Object.keys(w)) if (!(w[k] > 0)) w[k] = 0;
  return w;
}
