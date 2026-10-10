// Small geometry helpers shared by the animated SVG diagrams (States, Fan).
// A route is a list of segments; each is a straight line or a quadratic curve. We sample it to find
// how long it is and when a moving packet is inside a box, so boxes can light up as the packet passes.

export interface Pt { x: number; y: number }
export type Seg = { kind: 'L'; to: Pt } | { kind: 'Q'; c: Pt; to: Pt };
export interface Box { x: number; y: number; w: number; h: number }

export function routePath(start: Pt, segs: Seg[]): string {
  return [`M ${r(start.x)} ${r(start.y)}`, ...segs.map((s) => (s.kind === 'L' ? `L ${r(s.to.x)} ${r(s.to.y)}` : `Q ${r(s.c.x)} ${r(s.c.y)} ${r(s.to.x)} ${r(s.to.y)}`))].join(' ');
}

/** Points along the route, evenly spaced in parameter, with cumulative length. */
export function sample(start: Pt, segs: Seg[], per = 24): { p: Pt; d: number; seg: number }[] {
  const out = [{ p: start, d: 0, seg: 0 }];
  let from = start, d = 0;
  segs.forEach((s, k) => {
    for (let i = 1; i <= per; i++) {
      const t = i / per;
      const p = s.kind === 'L'
        ? { x: from.x + (s.to.x - from.x) * t, y: from.y + (s.to.y - from.y) * t }
        : { x: (1 - t) ** 2 * from.x + 2 * (1 - t) * t * s.c.x + t * t * s.to.x, y: (1 - t) ** 2 * from.y + 2 * (1 - t) * t * s.c.y + t * t * s.to.y };
      const prev = out[out.length - 1].p;
      d += Math.hypot(p.x - prev.x, p.y - prev.y);
      out.push({ p, d, seg: k });
    }
    from = s.to;
  });
  return out;
}

export const inBox = (p: Pt, b: Box) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;

/** Opacity keyframes (calcMode discrete) that are 1 whenever on(t) is true, for t in [0, 1]. */
export function windowsToKeys(on: (t: number) => boolean, steps = 240): { keyTimes: string; values: string } {
  const t: string[] = [], v: number[] = [];
  let last = -1;
  for (let s = 0; s <= steps; s++) {
    const x = on(s / steps) ? 1 : 0;
    if (s === 0 || x !== last) { t.push((s / steps).toFixed(4)); v.push(x); last = x; }
  }
  if (t[t.length - 1] !== '1.0000') { t.push('1.0000'); v.push(last); }
  return { keyTimes: t.join(';'), values: v.join(';') };
}

/** Split a label onto two lines near the middle when it is long. */
export function wrap(label: string, max = 14): string[] {
  if (label.length <= max || !label.includes(' ')) return [label];
  const mid = label.length / 2;
  let best = -1;
  for (let i = 0; i < label.length; i++) if (label[i] === ' ' && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
  return [label.slice(0, best), label.slice(best + 1)];
}

/** A stable short id for SVG defs, derived from the props. */
export const uid = (prefix: string, v: unknown) => prefix + [...JSON.stringify(v)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7).toString(36);

const r = (n: number) => Math.round(n * 10) / 10;
