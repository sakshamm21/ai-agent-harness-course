import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, BaseEdge, Controls, Handle, Position, addEdge, getBezierPath, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type EdgeProps, type Node, type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './lab.css';
import { simulate } from '../../lab/engine';
import { NODE_DEFS } from '../../lab/nodes';
import { NodeIcon, TONE } from './icons';
import type { Graph, NodeType, Scenario, SimOutput } from '../../lab/types';

interface Props { scenario: Scenario; lessonSlug: string; lessonTitle: string; nextUrl?: string; nextTitle?: string; base: string }

type FNode = Node<{ kind: NodeType; cfg: Record<string, any>; hot?: boolean; live?: boolean; focus?: boolean }>;
type Traffic = 'idle' | 'flow' | 'ok' | 'bad';
type FEdge = Edge<{ traffic?: Traffic }>;

const toFlow = (g: Graph): { nodes: FNode[]; edges: FEdge[] } => ({
  nodes: g.nodes.map((n, i) => ({
    id: n.id, type: 'lab', position: n.position ?? { x: i * 220, y: 100 },
    data: { kind: n.type, cfg: { ...NODE_DEFS[n.type].defaults, ...n.data } },
  })),
  edges: g.edges.map((e, i) => ({ id: e.id ?? `e${i}-${e.source}-${e.target}`, source: e.source, target: e.target, type: 'traffic' })),
});

const toGraph = (nodes: FNode[], edges: FEdge[]): Graph => ({
  nodes: nodes.map((n) => ({ id: n.id, type: n.data.kind, data: n.data.cfg, position: n.position })),
  edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
});

function summary(kind: NodeType, cfg: Record<string, any>): string {
  switch (kind) {
    case 'model': return `${cfg.tier}${cfg.reasoning ? ' · reasons' : ''}${cfg.parallelTools ? ' · parallel' : ''}${cfg.cachePrefix ? ' · cached' : ''}`;
    case 'loop': return `max ${cfg.maxTurns} turns${Number(cfg.maxCost) ? ` · $${cfg.maxCost}` : ''}`;
    case 'tool': return String(cfg.name || 'name me');
    case 'memory': return `${cfg.kind} · write ${cfg.writePolicy}`;
    case 'retriever': return `chunk ${cfg.chunkSize} · k=${cfg.topK}`;
    case 'judge': return `bar ${cfg.passBar}`;
    case 'guardrail': return cfg.rules || 'all rules';
    case 'compactor': return `${cfg.strategy} @ ${Math.round(Number(cfg.trigger) * 100)}%`;
    case 'subagent': case 'fallback': return String(cfg.tier);
    case 'permissions': return [cfg.deny && `deny ${cfg.deny}`, cfg.ask && `ask ${cfg.ask}`].filter(Boolean).join(' · ') || 'allow all';
    case 'router': return cfg.routes || 'no routes';
    case 'approval': return cfg.rule;
    case 'user': return 'sends the tasks';
    default: return '';
  }
}

function LabNodeView({ data, selected }: NodeProps<FNode>) {
  const def = NODE_DEFS[data.kind];
  return (
    <div className={`lab-node tone-${TONE[data.kind]}${selected ? ' sel' : ''}${data.hot ? ' hot' : ''}${data.live ? ' live' : ''}${data.focus ? ' focus' : ''}`}>
      {data.kind !== 'user' && <Handle type="target" position={Position.Left} />}
      <span className="nd-icon"><NodeIcon kind={data.kind} size={17} /></span>
      <span className="nd-text">
        <span className="nd-head">{def.label}</span>
        <span className="nd-sub">{summary(data.kind, data.cfg) || def.blurb}</span>
      </span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { lab: LabNodeView };

/** An edge that carries "requests": packets flow along it while a run plays, then it shows the outcome. */
function TrafficEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd, selected }: EdgeProps<FEdge>) {
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const t = data?.traffic ?? 'idle';
  const dur = t === 'flow' ? 0.9 : 2.4;
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} className={`tr-edge tr-${t}${selected ? ' sel' : ''}`} />
      {t !== 'idle' && [0, 1, 2].map((k) => (
        <circle key={`${t}-${k}`} r={t === 'flow' ? 4 : 3.5} className={`tr-packet tr-${t}`}>
          <animateMotion dur={`${dur}s`} begin={`${(k * dur) / 3}s`} repeatCount="indefinite" path={path} />
          {t === 'bad' && <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.55;0.7;1" dur={`${dur}s`} begin={`${(k * dur) / 3}s`} repeatCount="indefinite" />}
        </circle>
      ))}
    </>
  );
}
const edgeTypes = { traffic: TrafficEdge };
const reduceMotion = () => { try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; } };

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
  const [edges, setEdges, onEdgesChange] = useEdgesState<FEdge>(initial.edges);
  const [selected, setSelected] = useState<string | null>(null);
  const [out, setOut] = useState<SimOutput | null>(null);
  const [tab, setTab] = useState<'transcript' | 'trace' | 'metrics'>('transcript');
  const [hints, setHints] = useState(0);
  const [running, setRunning] = useState(false);
  const [ticker, setTicker] = useState<{ seed: number; of: number; solved: number; total: number } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearInterval(timer.current), []);
  const [viewRun, setViewRun] = useState(1);
  const [viewTask, setViewTask] = useState(scenario.tasks[0].id);
  const rf = useReactFlow();
  const wrapRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(1);

  useEffect(() => { store(saveKey, toGraph(nodes, edges)); }, [nodes, edges, saveKey]);

  const onConnect = useCallback((c: Connection) => setEdges((es) => addEdge({ ...c, type: 'traffic', id: `e-${c.source}-${c.target}-${Date.now()}` }, es)), [setEdges]);

  const addNode = useCallback((kind: NodeType, pos?: { x: number; y: number }) => {
    let position = pos;
    if (!position) {
      const r = wrapRef.current?.getBoundingClientRect();
      position = rf.screenToFlowPosition({ x: (r?.left ?? 0) + (r?.width ?? 400) * 0.36, y: (r?.top ?? 0) + (r?.height ?? 300) * 0.3 });
      // Clicking a part drops it left of centre, clear of the settings panel; step down until it is not sitting on top of another node.
      const taken = (p: { x: number; y: number }) => rf.getNodes().some((n) => Math.abs(n.position.x - p.x) < 190 && Math.abs(n.position.y - p.y) < 64);
      for (let k = 0; k < 12 && taken(position); k++) position = { x: position.x, y: position.y + 76 };
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

  const setTraffic = (traffic: (e: FEdge) => Traffic) => setEdges((es) => es.map((e) => ({ ...e, type: 'traffic', data: { ...e.data, traffic: traffic(e) } })));

  const finish = (result: SimOutput) => {
    setOut(result);
    setRunning(false);
    setTicker(null);
    const hot = new Set(result.hotNodes);
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, live: false, hot: hot.has(n.id) } })));
    setTraffic((e) => (hot.has(e.target) || hot.has(e.source) ? 'bad' : 'ok'));
    if (result.passed) {
      const p = (store('fah-progress') as Record<string, number> | null) ?? {};
      p[lessonSlug] = 1;
      store('fah-progress', p);
    }
  };

  // Simulate every seed at once, then replay the seeds on the canvas so you can watch the traffic.
  const run = () => {
    window.clearInterval(timer.current);
    const result = simulate(scenario, toGraph(nodes, edges));
    const seeds = Math.max(1, ...result.results.map((r) => r.run));
    if (reduceMotion()) { finish(result); return; }
    setRunning(true);
    setOut(null);
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, hot: false, live: true } })));
    setTraffic(() => 'flow');
    let seed = 0;
    const step = Math.max(25, Math.min(60, 1100 / seeds));
    timer.current = window.setInterval(() => {
      seed++;
      const done = result.results.filter((r) => r.run <= seed);
      setTicker({ seed, of: seeds, solved: done.filter((r) => r.success).length, total: done.length });
      if (seed >= seeds) { window.clearInterval(timer.current); window.setTimeout(() => finish(result), 250); }
    }, step);
  };

  const events = out?.events.filter((e) => e.run === viewRun && e.task === viewTask) ?? [];

  // Step through one task's transcript: each event lights up the part on the canvas that produced it.
  const [step, setStep] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setStep(null); setPlaying(false); }, [out, viewRun, viewTask]);
  useEffect(() => {
    const focusId = step === null ? undefined : events[step]?.nodeId;
    setNodes((ns) => ns.map((n) => (!!n.data.focus === (n.id === focusId) ? n : { ...n, data: { ...n.data, focus: n.id === focusId } })));
    if (step !== null) transcriptRef.current?.querySelector(`[data-ev="${step}"]`)?.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);
  useEffect(() => {
    if (!playing) return;
    const t = window.setTimeout(() => {
      setStep((s) => { const nx = s === null ? 0 : s + 1; if (nx >= events.length - 1) setPlaying(false); return Math.min(nx, events.length - 1); });
    }, step === null ? 0 : 900);
    return () => window.clearTimeout(t);
  }, [playing, step, events.length]);
  const firstBad = events.find((e) => e.bad && e.kind !== 'result');

  return (
    <div className="lab agentlab" data-state={running ? 'running' : out ? 'done' : 'idle'}>
      <div className="lab-side">
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

        <div className="runbar">
          <button type="button" className="btn run" onClick={run} disabled={running}>
            {running ? <span className="spin" aria-hidden="true" /> : <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M7 4.5v15l12.5-7.5L7 4.5Z" /></svg>}
            {running ? 'Running…' : `Run ${scenario.runs ?? 20}×`}
            {!running && <small>seeds 1–{scenario.runs ?? 20}</small>}
          </button>
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
              <div className="stepbar">
                <button type="button" className="btn small" onClick={() => { if (step !== null && step >= events.length - 1) setStep(null); setPlaying((p) => !p); }}>
                  {playing ? '❚❚ Pause' : step === null ? '▶ Step through this run' : step >= events.length - 1 ? '↺ Replay' : '▶ Resume'}
                </button>
                <button type="button" className="btn ghost small" aria-label="Previous event" disabled={!step} onClick={() => { setPlaying(false); setStep((s) => Math.max(0, (s ?? 0) - 1)); }}>←</button>
                <button type="button" className="btn ghost small" aria-label="Next event" disabled={step !== null && step >= events.length - 1} onClick={() => { setPlaying(false); setStep((s) => (s === null ? 0 : Math.min(events.length - 1, s + 1))); }}>→</button>
                <span className="step-count">{step === null ? `${events.length} events · the canvas lights up the part behind each one` : `Event ${step + 1} of ${events.length}`}</span>
              </div>
            )}
            {tab === 'transcript' && (
              <div className={`transcript${step !== null ? ' stepping' : ''}`} ref={transcriptRef}>
                {events.map((e, i) => (
                  <div key={i} data-ev={i} onClick={() => { setPlaying(false); setStep(i); }}
                    className={`bubble k-${e.kind}${e.bad ? ' bad' : ''}${step === i ? ' current' : ''}${step !== null && i > step ? ' later' : ''}`}>
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
      <div className="lab-main">
        <div className="lab-grid">
          <aside className="palette" aria-label="Parts">
            <div className="pal-title">Add a part</div>
            {scenario.palette.map((kind) => {
              const def = NODE_DEFS[kind];
              return (
                <button key={kind} type="button" className="pal-item" draggable
                  onDragStart={(e) => { e.dataTransfer.setData('application/x-lab-node', kind); e.dataTransfer.effectAllowed = 'move'; }}
                  onClick={() => addNode(kind)} title={def.blurb}>
                  <span className={`nd-icon tone-${TONE[kind]}`}><NodeIcon kind={kind} size={14} /></span><span>{def.label}</span><span className="pal-plus" aria-hidden="true">+</span>
                </button>
              );
            })}
            <p className="pal-help">Click or drag a part onto the canvas. Drag from a node's right dot to another node's left dot to wire them.</p>
          </aside>

          <div className="canvas" ref={wrapRef} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }} onDrop={onDrop}>
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onSelectionChange={({ nodes: s }) => setSelected(s[0]?.id ?? null)}
              fitView fitViewOptions={{ padding: 0.12, maxZoom: 1.1 }} minZoom={0.3} proOptions={{ hideAttribution: true }}
              deleteKeyCode={['Backspace', 'Delete']}
            >
              <Background gap={22} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
            {(ticker || out) && (
              <div className={`sim-ticker${out ? (out.passed ? ' pass' : ' fail') : ''}`} role="status" aria-live="polite">
                {ticker
                  ? <><span className="spin" aria-hidden="true" />Seed {ticker.seed} / {ticker.of} · {Math.round((ticker.solved / Math.max(1, ticker.total)) * 100)}% solved</>
                  : <>{out!.passed ? '✓ All goals met' : `✗ ${out!.goals.filter((g) => !g.pass).length} goal${out!.goals.filter((g) => !g.pass).length === 1 ? '' : 's'} missed`} · {Math.round(out!.metrics.success_rate * 100)}% solved</>}
              </div>
            )}
          </div>

          <aside className="inspector" aria-label="Inspector">
            {sel ? (
              <>
                <div className="ins-title">
                  <span className={`nd-icon tone-${TONE[sel.data.kind]}`}><NodeIcon kind={sel.data.kind} size={15} /></span>
                  <span>{NODE_DEFS[sel.data.kind].label}</span>
                  <button type="button" className="ins-close" aria-label="Close settings" onClick={() => { setSelected(null); setNodes((ns) => ns.map((n) => (n.selected ? { ...n, selected: false } : n))); }}>×</button>
                </div>
                <p className="ins-blurb">{NODE_DEFS[sel.data.kind].blurb}</p>
                {NODE_DEFS[sel.data.kind].fields.length === 0 && <p className="ins-none">Nothing to set on this part. Wire it to the next one.</p>}
                {NODE_DEFS[sel.data.kind].fields.map((f) => {
                  const v = sel.data.cfg[f.key];
                  const id = `f-${sel.id}-${f.key}`;
                  return (
                    <label key={f.key} className={`field field-${f.kind}`} htmlFor={id}>
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
                <button type="button" className="btn ghost small danger" onClick={removeSelected}>Remove node</button>
              </>
            ) : (
              <p className="ins-empty">Select a node to change its settings.</p>
            )}
          </aside>
        </div>

      </div>
    </div>
  );
}

export default function LabApp(props: Props) {
  return <ReactFlowProvider><Lab {...props} /></ReactFlowProvider>;
}
