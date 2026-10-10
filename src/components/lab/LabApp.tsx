import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Controls, Handle, Position, addEdge, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node, type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './lab.css';
import { simulate } from '../../lab/engine';
import { NODE_DEFS } from '../../lab/nodes';
import type { Graph, NodeType, Scenario, SimOutput } from '../../lab/types';

interface Props { scenario: Scenario; lessonSlug: string; lessonTitle: string; nextUrl?: string; nextTitle?: string; base: string }

type FNode = Node<{ kind: NodeType; cfg: Record<string, any>; hot?: boolean }>;

const toFlow = (g: Graph): { nodes: FNode[]; edges: Edge[] } => ({
  nodes: g.nodes.map((n, i) => ({
    id: n.id, type: 'lab', position: n.position ?? { x: i * 220, y: 100 },
    data: { kind: n.type, cfg: { ...NODE_DEFS[n.type].defaults, ...n.data } },
  })),
  edges: g.edges.map((e, i) => ({ id: e.id ?? `e${i}-${e.source}-${e.target}`, source: e.source, target: e.target, animated: false })),
});

const toGraph = (nodes: FNode[], edges: Edge[]): Graph => ({
  nodes: nodes.map((n) => ({ id: n.id, type: n.data.kind, data: n.data.cfg, position: n.position })),
  edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
});

function summary(kind: NodeType, cfg: Record<string, any>): string {
  switch (kind) {
    case 'model': return `${cfg.tier}${cfg.reasoning ? ' · reasons' : ''}${cfg.parallelTools ? ' · parallel' : ''}${cfg.cachePrefix ? ' · cached' : ''}`;
    case 'loop': return `max ${cfg.maxTurns} turns${Number(cfg.maxCost) ? ` · $${cfg.maxCost}` : ''}`;
    case 'tool': return String(cfg.name || 'unnamed');
    case 'memory': return `${cfg.kind} · write ${cfg.writePolicy}`;
    case 'retriever': return `chunk ${cfg.chunkSize} · k=${cfg.topK}`;
    case 'judge': return `bar ${cfg.passBar}`;
    case 'guardrail': return cfg.rules || 'all rules';
    case 'compactor': return `${cfg.strategy} @ ${Math.round(Number(cfg.trigger) * 100)}%`;
    case 'subagent': case 'fallback': return String(cfg.tier);
    case 'permissions': return [cfg.deny && `deny ${cfg.deny}`, cfg.ask && `ask ${cfg.ask}`].filter(Boolean).join(' · ') || 'allow all';
    case 'router': return cfg.routes || 'no routes';
    case 'approval': return cfg.rule;
    default: return '';
  }
}

function LabNodeView({ data, selected }: NodeProps<FNode>) {
  const def = NODE_DEFS[data.kind];
  return (
    <div className={`lab-node${selected ? ' sel' : ''}${data.hot ? ' hot' : ''}`}>
      {data.kind !== 'user' && <Handle type="target" position={Position.Left} />}
      <div className="ln-head"><span aria-hidden="true">{def.icon}</span>{def.label}</div>
      <div className="ln-sub">{summary(data.kind, data.cfg)}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { lab: LabNodeView };

const fmt$ = (n: number) => (n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(3)}`);
function fmtMetric(metric: string, v: number) {
  if (!isFinite(v)) return '∞';
  if (metric.includes('rate') || metric === 'tool_accuracy') return `${Math.round(v * 100)}%`;
  if (metric.includes('cost')) return fmt$(v);
  if (metric === 'avg_latency') return `${v.toFixed(1)}s`;
  if (metric === 'avg_tokens' || metric === 'max_context') return Math.round(v).toLocaleString('en-US');
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function store(key: string, value?: any) {
  try {
    if (value === undefined) return JSON.parse(localStorage.getItem(key) || 'null');
    localStorage.setItem(key, JSON.stringify(value));
  } catch { /* storage may be unavailable */ }
  return null;
}

function Lab({ scenario, lessonSlug, lessonTitle, nextUrl, nextTitle, base }: Props) {
  const saveKey = `fah-lab-${scenario.id}`;
  const initial = useMemo(() => toFlow((store(saveKey) as Graph | null) ?? scenario.starter), [scenario, saveKey]);
  const [nodes, setNodes, onNodesChange] = useNodesState<FNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.edges);
  const [selected, setSelected] = useState<string | null>(null);
  const [out, setOut] = useState<SimOutput | null>(null);
  const [tab, setTab] = useState<'transcript' | 'trace' | 'metrics'>('transcript');
  const [hints, setHints] = useState(0);
  const [running, setRunning] = useState(false);
  const [viewRun, setViewRun] = useState(1);
  const [viewTask, setViewTask] = useState(scenario.tasks[0].id);
  const rf = useReactFlow();
  const wrapRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(1);

  useEffect(() => { store(saveKey, toGraph(nodes, edges)); }, [nodes, edges, saveKey]);

  const onConnect = useCallback((c: Connection) => setEdges((es) => addEdge({ ...c, id: `e-${c.source}-${c.target}-${Date.now()}` }, es)), [setEdges]);

  const addNode = useCallback((kind: NodeType, pos?: { x: number; y: number }) => {
    let position = pos;
    if (!position) {
      const r = wrapRef.current?.getBoundingClientRect();
      position = rf.screenToFlowPosition({ x: (r?.left ?? 0) + (r?.width ?? 400) / 2, y: (r?.top ?? 0) + (r?.height ?? 300) / 2 });
    }
    const id = `${kind}-${Date.now().toString(36)}-${idRef.current++}`;
    const cfg = { ...NODE_DEFS[kind].defaults };
    if (kind === 'tool') cfg.name = '';
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), { id, type: 'lab', position, selected: true, data: { kind, cfg } }]);
    setSelected(id);
  }, [rf, setNodes]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData('application/x-lab-node') as NodeType;
    if (!kind) return;
    addNode(kind, rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  }, [addNode, rf]);

  const sel = nodes.find((n) => n.id === selected);
  const updateCfg = (key: string, value: any) =>
    setNodes((ns) => ns.map((n) => (n.id === selected ? { ...n, data: { ...n.data, cfg: { ...n.data.cfg, [key]: value } } } : n)));
  const removeSelected = () => {
    if (!selected) return;
    setNodes((ns) => ns.filter((n) => n.id !== selected));
    setEdges((es) => es.filter((e) => e.source !== selected && e.target !== selected));
    setSelected(null);
  };

  const load = (g: Graph) => {
    const f = toFlow(g);
    setNodes(f.nodes); setEdges(f.edges); setOut(null); setSelected(null);
    setTimeout(() => rf.fitView({ padding: 0.2 }), 30);
  };

  const run = () => {
    setRunning(true);
    setTimeout(() => {
      const result = simulate(scenario, toGraph(nodes, edges));
      setOut(result);
      setRunning(false);
      setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, hot: result.hotNodes.includes(n.id) } })));
      setEdges((es) => es.map((e) => ({ ...e, animated: true })));
      if (result.passed) {
        const p = (store('fah-progress') as Record<string, number> | null) ?? {};
        p[lessonSlug] = p[lessonSlug] || Date.now();
        store('fah-progress', p);
      }
    }, 20);
  };

  const events = out?.events.filter((e) => e.run === viewRun && e.task === viewTask) ?? [];
  const firstBad = events.find((e) => e.bad && e.kind !== 'result');

  return (
    <div className="lab">
      <header className="lab-head">
        <a href={`${base}/c/${lessonSlug}/`} className="back">← {lessonTitle} lesson</a>
        <h1>Build: {scenario.title}</h1>
        <p className="brief">{scenario.brief}</p>
        <ul className="goals" aria-label="Goals">
          {scenario.goals.map((g) => {
            const r = out?.goals.find((x) => x.id === g.id);
            return (
              <li key={g.id} className={r ? (r.pass ? 'pass' : 'fail') : ''}>
                <span className="dot" aria-hidden="true">{r ? (r.pass ? '✓' : '✗') : '○'}</span>
                {g.label}
                {r && <span className="actual">now {fmtMetric(g.metric, r.actual)}</span>}
              </li>
            );
          })}
        </ul>
      </header>

      {out?.passed && (
        <div className="passed" role="status">
          <div><strong>Passed.</strong> {scenario.explain}</div>
          {nextUrl && <a className="btn small" href={nextUrl}>Next: {nextTitle} →</a>}
        </div>
      )}

      <div className="lab-grid">
        <aside className="palette" aria-label="Parts">
          <div className="pal-title">Parts</div>
          {scenario.palette.map((kind) => {
            const def = NODE_DEFS[kind];
            return (
              <button key={kind} type="button" className="pal-item" draggable
                onDragStart={(e) => { e.dataTransfer.setData('application/x-lab-node', kind); e.dataTransfer.effectAllowed = 'move'; }}
                onClick={() => addNode(kind)} title={def.blurb}>
                <span aria-hidden="true">{def.icon}</span><span>{def.label}</span>
              </button>
            );
          })}
          <p className="pal-help">Click or drag a part onto the canvas. Drag from a node's right dot to another node's left dot to wire them.</p>
        </aside>

        <div className="canvas" ref={wrapRef} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onSelectionChange={({ nodes: s }) => setSelected(s[0]?.id ?? null)}
            fitView fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }} minZoom={0.3} proOptions={{ hideAttribution: true }}
            deleteKeyCode={['Backspace', 'Delete']}
          >
            <Background gap={22} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <aside className="inspector" aria-label="Inspector">
          {sel ? (
            <>
              <div className="ins-title"><span aria-hidden="true">{NODE_DEFS[sel.data.kind].icon}</span> {NODE_DEFS[sel.data.kind].label}</div>
              <p className="ins-blurb">{NODE_DEFS[sel.data.kind].blurb}</p>
              {NODE_DEFS[sel.data.kind].fields.map((f) => {
                const v = sel.data.cfg[f.key];
                const id = `f-${sel.id}-${f.key}`;
                return (
                  <label key={f.key} className="field" htmlFor={id}>
                    <span>{f.label}{f.kind === 'range' ? `: ${v}` : ''}</span>
                    {f.kind === 'select' && <select id={id} value={v} onChange={(e) => updateCfg(f.key, e.target.value)}>{f.options!.map((o) => <option key={o}>{o}</option>)}</select>}
                    {f.kind === 'number' && <input id={id} type="number" value={v} min={f.min} max={f.max} step={f.step ?? 1} onChange={(e) => updateCfg(f.key, e.target.value === '' ? '' : Number(e.target.value))} />}
                    {f.kind === 'range' && <input id={id} type="range" value={v} min={f.min} max={f.max} step={f.step} onChange={(e) => updateCfg(f.key, Number(e.target.value))} />}
                    {f.kind === 'text' && <input id={id} type="text" value={v} onChange={(e) => updateCfg(f.key, e.target.value)} />}
                    {f.kind === 'textarea' && <textarea id={id} rows={4} value={v} onChange={(e) => updateCfg(f.key, e.target.value)} />}
                    {f.kind === 'bool' && <input id={id} type="checkbox" checked={!!v} onChange={(e) => updateCfg(f.key, e.target.checked)} />}
                    {f.help && <small>{f.help}</small>}
                  </label>
                );
              })}
              <button type="button" className="btn ghost small" onClick={removeSelected}>Remove node</button>
            </>
          ) : (
            <p className="ins-empty">Select a node to change its settings.</p>
          )}
        </aside>
      </div>

      <div className="runbar">
        <button type="button" className="btn" onClick={run} disabled={running}>{running ? 'Running…' : `▶ Run ${scenario.runs ?? 20}× (seeds 1–${scenario.runs ?? 20})`}</button>
        <button type="button" className="btn ghost small" onClick={() => load(scenario.starter)}>Reset</button>
        <button type="button" className="btn ghost small" onClick={() => setHints((h) => Math.min(h + 1, scenario.hints.length))} disabled={hints >= scenario.hints.length}>Hint ({hints}/{scenario.hints.length})</button>
        {hints >= 2 && <button type="button" className="btn ghost small" onClick={() => load(scenario.solution)}>Show solution</button>}
      </div>
      {hints > 0 && <ol className="hints">{scenario.hints.slice(0, hints).map((h, i) => <li key={i}>{h}</li>)}</ol>}

      {out && (
        <section className="results">
          <div className="tabs" role="tablist">
            {(['transcript', 'trace', 'metrics'] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>
            ))}
            {tab !== 'metrics' && (
              <span className="pickers">
                <select aria-label="Run" value={viewRun} onChange={(e) => setViewRun(Number(e.target.value))}>{[1, 2, 3].map((r) => <option key={r} value={r}>Run {r}</option>)}</select>
                <select aria-label="Task" value={viewTask} onChange={(e) => setViewTask(e.target.value)}>{scenario.tasks.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select>
              </span>
            )}
          </div>
          {tab === 'transcript' && (
            <div className="transcript">
              {events.map((e, i) => (
                <div key={i} className={`bubble k-${e.kind}${e.bad ? ' bad' : ''}`}>
                  <span className="who">{e.kind === 'user' ? 'User' : e.kind === 'model' ? `Model · turn ${e.turn}` : e.kind.replace('_', ' ')}</span>
                  <span className="txt">{e.text}</span>
                </div>
              ))}
            </div>
          )}
          {tab === 'trace' && (
            <div className="trace">
              {firstBad && <p className="trace-alert">First problem: turn {firstBad.turn}. {firstBad.text}</p>}
              <table>
                <thead><tr><th>Turn</th><th>Step</th><th>Context</th><th>Cost</th><th>Time</th></tr></thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr key={i} className={e.bad ? 'bad' : ''}>
                      <td>{e.turn}</td><td>{e.kind.replace('_', ' ')}: {e.text.length > 90 ? e.text.slice(0, 88) + '…' : e.text}</td>
                      <td>{e.ctx.toLocaleString('en-US')}</td><td>{fmt$(e.cost)}</td><td>{e.latency}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === 'metrics' && (
            <div className="metrics">
              <table>
                <tbody>
                  {([
                    ['success_rate', 'Success rate'], ['avg_turns', 'Avg turns'], ['avg_cost', 'Avg cost per task'], ['avg_tokens', 'Avg input tokens'],
                    ['avg_latency', 'Avg time per task'], ['max_context', 'Peak context (tokens)'], ['incidents', 'Incidents'], ['approvals_per_task', 'Human approvals per task'],
                    ['tool_accuracy', 'Useful tool calls'], ['stopped_rate', 'Stopped by a cap'],
                  ] as const).map(([k, label]) => <tr key={k}><th>{label}</th><td>{fmtMetric(k, out.metrics[k])}</td></tr>)}
                </tbody>
              </table>
              <p className="note">{out.results.length} task runs. Prices are illustrative "sim prices" ($1/$3/$15 per million input tokens for small/medium/large).</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default function LabApp(props: Props) {
  return <ReactFlowProvider><Lab {...props} /></ReactFlowProvider>;
}
