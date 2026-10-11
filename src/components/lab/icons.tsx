import type { NodeType } from '../../lab/types';

// One line icon per part, drawn on a 24px grid with the current text colour.
const PATHS: Record<NodeType, string> = {
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20a7.5 7.5 0 0 1 15 0',
  model: 'M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9L11 3ZM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z',
  loop: 'M17 2.5l3.5 3.5L17 9.5M3.5 11.5V10a4 4 0 0 1 4-4h13M7 21.5L3.5 18 7 14.5M20.5 12.5V14a4 4 0 0 1-4 4h-13',
  tool: 'M14.7 6.3a4 4 0 0 0-5.2 5.2l-5.9 5.9a2.1 2.1 0 1 0 3 3l5.9-5.9a4 4 0 0 0 5.2-5.2l-2.6 2.6-2.4-.6-.6-2.4 2.6-2.6Z',
  memory: 'M4 6.5C4 5 7.6 3.8 12 3.8S20 5 20 6.5 16.4 9.2 12 9.2 4 8 4 6.5ZM4 6.5V12c0 1.5 3.6 2.7 8 2.7s8-1.2 8-2.7V6.5M4 12v5.5c0 1.5 3.6 2.7 8 2.7s8-1.2 8-2.7V12',
  retriever: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM20 20l-4.8-4.8M8 9h5M8 12h3',
  router: 'M4 12h6M10 12c3 0 3-6 6-6h4M10 12c3 0 3 6 6 6h4M17.5 3.5L20 6l-2.5 2.5M17.5 15.5L20 18l-2.5 2.5',
  judge: 'M12 4v16M7 20h10M5 7h14M5 7l-2.5 6a2.8 2.8 0 0 0 5 0L5 7ZM19 7l-2.5 6a2.8 2.8 0 0 0 5 0L19 7Z',
  guardrail: 'M12 3l7.5 2.8v5.4c0 4.5-3.1 8.2-7.5 9.8-4.4-1.6-7.5-5.3-7.5-9.8V5.8L12 3ZM9 12l2.2 2.2 4-4.2',
  approval: 'M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v8.5a6.5 6.5 0 0 1-6.5 6.5 6 6 0 0 1-4.8-2.4L3.4 15.5a1.6 1.6 0 0 1 2.5-2L8 15.5',
  subagent: 'M9 3.5h6v5H9v-5ZM3.5 15.5h6v5h-6v-5ZM14.5 15.5h6v5h-6v-5ZM12 8.5V12M6.5 15.5V12h11v3.5',
  permissions: 'M6.5 11h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 18.5v-6A1.5 1.5 0 0 1 6.5 11ZM8.5 11V8a3.5 3.5 0 0 1 7 0v3M12 14.5v2',
  compactor: 'M4 4h16M4 20h16M12 6.5V11M9.5 8.5L12 11l2.5-2.5M12 17.5V13M9.5 15.5L12 13l2.5 2.5',
  fallback: 'M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17ZM12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM6 6l3.5 3.5M18 6l-3.5 3.5M6 18l3.5-3.5M18 18l-3.5-3.5',
};

/** Colour family of each part: who talks, who thinks, who acts, who stores, who guards. */
export const TONE: Record<NodeType, string> = {
  user: 'talk', model: 'think', fallback: 'think', subagent: 'think',
  loop: 'flow', router: 'flow', compactor: 'flow',
  tool: 'act', memory: 'store', retriever: 'store',
  judge: 'guard', guardrail: 'guard', approval: 'guard', permissions: 'guard',
};

export function NodeIcon({ kind, size = 16 }: { kind: NodeType; size?: number }) {
  return (
    <svg className="nd-svg" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[kind]} />
    </svg>
  );
}
