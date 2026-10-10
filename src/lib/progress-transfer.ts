// Moving progress between browsers without any server: export everything the site keeps in
// localStorage to a JSON file, import it elsewhere. Nothing leaves the learner's device.

export const TRANSFER_KEY = /^fah-(progress|code-[A-Za-z0-9_-]+|lab-[A-Za-z0-9_-]+)$/;
export const FORMAT = 'free-agent-harness-progress';
const MAX_BYTES = 5_000_000;

export interface ProgressFile { format: typeof FORMAT; version: 1; exportedAt: string; data: Record<string, string> }

export function buildExport(local: Record<string, string>, now = new Date()): ProgressFile {
  const data: Record<string, string> = {};
  for (const [k, v] of Object.entries(local)) if (TRANSFER_KEY.test(k)) data[k] = v;
  return { format: FORMAT, version: 1, exportedAt: now.toISOString(), data };
}

function parseProgress(raw: string | undefined): Record<string, number> {
  try {
    const p = JSON.parse(raw || '{}');
    if (!p || typeof p !== 'object' || Array.isArray(p)) return {};
    return Object.fromEntries(Object.entries(p).filter(([, v]) => typeof v === 'number' && v > 0)) as Record<string, number>;
  } catch { return {}; }
}

/** Union of two progress maps (completion time in ms, or 1 from older builds), keeping the earliest real time. */
export function mergeProgress(a: string | undefined, b: string | undefined): string {
  const out = parseProgress(a);
  for (const [k, v] of Object.entries(parseProgress(b))) {
    const cur = out[k];
    if (cur === undefined) out[k] = v;
    else if (cur > 1 && v > 1) out[k] = Math.min(cur, v);
    else if (v > 1) out[k] = v;
  }
  return JSON.stringify(out);
}

/**
 * Validate an imported file and work out what to write. Completed lessons are merged, so importing
 * never un-completes anything; saved lab graphs and code from the file replace the ones here.
 */
export function planImport(text: string, local: Record<string, string>): { writes: Record<string, string>; completed: number } {
  if (text.length > MAX_BYTES) throw new Error('That file is too large to be a progress file.');
  let file: Partial<ProgressFile>;
  try { file = JSON.parse(text); } catch { throw new Error("That file isn't a progress file (it isn't JSON)."); }
  if (!file || file.format !== FORMAT || typeof file.data !== 'object' || !file.data) throw new Error("That file isn't a Free Agent Harness progress file.");
  const writes: Record<string, string> = {};
  for (const [k, v] of Object.entries(file.data)) {
    if (!TRANSFER_KEY.test(k) || typeof v !== 'string') continue;
    writes[k] = k === 'fah-progress' ? mergeProgress(local[k], v) : v;
  }
  const completed = Object.keys(parseProgress(writes['fah-progress'] ?? local['fah-progress'])).length;
  return { writes, completed };
}
