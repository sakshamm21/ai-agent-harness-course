// Agent Lab types. The engine is pure: graph + scenario + seed -> events + result.

export type NodeType =
  | 'user' | 'model' | 'loop' | 'tool' | 'memory' | 'retriever' | 'router'
  | 'judge' | 'guardrail' | 'approval' | 'subagent' | 'permissions'
  | 'compactor' | 'fallback';

export interface LabNode {
  id: string;
  type: NodeType;
  data: Record<string, any>;
  position?: { x: number; y: number };
}

export interface LabEdge { id?: string; source: string; target: string }

export interface Graph { nodes: LabNode[]; edges: LabEdge[] }

export type Op = '==' | '!=' | '>' | '>=' | '<' | '<=' | 'in';

/** Conditions are evaluated against the graph and the live run state. */
export type Cond =
  | { has: NodeType | NodeType[] }                       // node(s) present and wired
  | { tool: string }                                     // a tool node with this name is present
  | { setting: string; op: Op; value: any }              // "model.tier", "loop.maxTurns", "tool:search.errorMode"
  | { toolQuality: string; op: Op; value: number }       // rubric score 0..1 of a tool description
  | { edge: [NodeType, NodeType] }                       // a wire from a node of type A to type B
  | { state: StateFlag }
  | { turn: Op; value: number }
  | { called: string }                                   // this tool has already succeeded in this task
  | { task: string }
  | { tag: string }                                      // task has this tag
  | { all: Cond[] } | { any: Cond[] } | { not: Cond };

export type StateFlag =
  | 'ready'            // every tool in task.needs has been called successfully
  | 'first_turn'
  | 'over_budget'      // context exceeded the window at least once and no compactor saved it
  | 'lost_instructions'// truncation dropped the original task
  | 'tool_error'       // the last tool call failed
  | 'tool_error_raw'   // ... and returned a raw stack trace
  | 'tool_error_actionable'
  | 'injected'         // the agent has read untrusted content containing instructions
  | 'repeating'        // the last two actions were identical
  | 'judged_fail'      // a judge just rejected the answer
  | 'compacted'        // the context has been compacted at least once
  | 'resumed';         // the run was resumed from saved state

export interface Modifier {
  when: Cond;
  /** add to the weight of each action */
  shift?: Record<string, number>;
  /** multiply the weight of each action */
  scale?: Record<string, number>;
  /** set the weight of each action */
  set?: Record<string, number>;
  note?: string;
}

export type ActionKind =
  | 'tool'        // calls a tool node (by `tool` name)
  | 'answer'      // finishes the task; `correct` says if the answer is right
  | 'repeat'      // repeats the previous call, no progress
  | 'think'       // reasoning / planning step, no tool
  | 'injection'   // follows an injected instruction (incident unless intercepted)
  | 'dangerous';  // a destructive or irreversible action the task did not need

export interface ActionDef {
  kind: ActionKind;
  text: string;                 // shown in the transcript
  tool?: string;                // for kind=tool (and optionally dangerous/injection)
  correct?: boolean;            // for kind=answer
  tokens?: number;              // tokens this step adds to the context (default 300)
  outputTokens?: number;        // model output tokens (default 150)
  latencyMs?: number;           // extra latency for this step
  batch?: number;               // number of independent calls this step represents
  offloadable?: boolean;        // a subagent can absorb these tokens
  untrusted?: boolean;          // reading this content sets the `injected` flag
  sideEffect?: boolean;         // retrying a failed call may duplicate the effect
  irreversible?: boolean;       // an approval node intercepts it
  legit?: boolean;              // for irreversible actions: the human approves it
  guardTag?: string;            // guardrail rules matching this tag block it
  incident?: string;            // label for the incident if it goes through
}

export interface Task {
  id: string;
  label: string;
  prompt: string;
  needs?: string[];             // tools to call successfully before `ready`
  tokensPerTurn?: number;       // overrides action tokens when set
  tags?: string[];
  weight?: number;
}

export type Metric =
  | 'success_rate' | 'avg_turns' | 'avg_cost' | 'avg_tokens' | 'avg_latency'
  | 'incidents' | 'incident_rate' | 'approvals_per_task' | 'stopped_rate'
  | 'max_context' | 'tool_accuracy' | 'cost_per_success';

export interface Goal { id: string; label: string; metric: Metric; op: Op; value: number }

export interface Scenario {
  id: string;
  title: string;
  brief: string;
  palette: NodeType[];
  starter: Graph;
  solution: Graph;
  runs?: number;                // seeds 1..runs (default 20)
  window?: number;              // context window in tokens (default from model tier)
  systemTokens?: number;        // system prompt + tool schemas (default 1200)
  hardCap?: number;             // absolute turn cap (default 60); hitting it = runaway incident
  outageRate?: number;          // chance a primary model call errors (default 0)
  tasks: Task[];
  actions: Record<string, ActionDef>;
  policy: { base: Record<string, number>; modifiers: Modifier[] };
  goals: Goal[];
  hints: string[];
  explain?: string;             // shown after passing
}

export type EventKind =
  | 'user' | 'model' | 'tool' | 'tool_error' | 'system' | 'blocked'
  | 'approval' | 'incident' | 'judge' | 'compact' | 'result';

export interface SimEvent {
  run: number;
  task: string;
  turn: number;
  kind: EventKind;
  text: string;
  ctx: number;            // context tokens after this step
  cost: number;           // cumulative $ for this task
  latency: number;        // cumulative seconds for this task
  nodeId?: string;        // node to highlight
  bad?: boolean;
}

export interface TaskResult {
  run: number;
  task: string;
  success: boolean;
  outcome: 'correct' | 'wrong' | 'stopped' | 'runaway' | 'incident' | 'outage' | 'blocked';
  turns: number;
  tokens: number;         // total input tokens billed
  cost: number;
  latency: number;
  incidents: number;
  approvals: number;
  maxContext: number;
  toolCalls: number;
  rightToolCalls: number;
}

export type Metrics = Record<Metric, number>;

export interface SimOutput {
  events: SimEvent[];
  results: TaskResult[];
  metrics: Metrics;
  goals: { id: string; label: string; pass: boolean; actual: number }[];
  passed: boolean;
  hotNodes: string[];     // nodes involved in failures (for the red pulse)
}
