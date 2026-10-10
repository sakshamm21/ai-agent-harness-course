// Fast content check that does not need a full Astro build (safe to run in parallel).
// node scripts/validate-content.mjs [slug ...]
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import { compile, evaluate } from '@mdx-js/mdx';
import * as runtime from 'react/jsx-runtime';
import { z } from 'zod';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const curriculum = JSON.parse(fs.readFileSync(path.join(ROOT, 'scripts/curriculum.json'), 'utf8'));
const slugs = new Set(curriculum.map((c) => c.slug));
const only = new Set(process.argv.slice(2));

const lesson = z.object({
  title: z.string(), section: z.enum(['foundations', 'tools', 'harness', 'memory', 'patterns', 'reliability', 'operate', 'cases']),
  order: z.number().int().min(1).max(54), tagline: z.string(), realWorld: z.string(),
  build: z.object({ type: z.enum(['lab', 'code', 'none']), scenario: z.string().optional() }),
  terms: z.array(z.object({ term: z.string(), def: z.string() })).default([]),
  usedIn: z.array(z.string().regex(/^(nanoharness|supportbot|deepresearch)\/\d+$/)).default([]),
  readingMinutes: z.number().int().positive(), updated: z.union([z.string(), z.date()]),
  quiz: z.array(z.object({ q: z.string(), options: z.array(z.string()).min(2), answer: z.number().int().min(0), why: z.string() })).length(3),
  reading: z.array(z.object({ title: z.string(), url: z.string().url() })).default([]),
}).strict();

// Props checks for the figure components, so a typo shows up here rather than as a broken drawing.
const KINDS = new Set([undefined, 'hl', 'good', 'bad']);
const ROLES = new Set(['user', 'model', 'tool', 'result', 'system', 'error', 'human', 'note']);
const need = (cond, msg) => { if (!cond) throw new Error(msg); };
const num = (v) => typeof v === 'number' && Number.isFinite(v);
const node = (x, what) => { need(x && typeof x.label === 'string', `${what} needs a label`); need(KINDS.has(x.kind), `${what}: kind must be hl, good or bad`); };
const CHECKS = {
  Callout: () => {},
  Flow: (p) => { need(Array.isArray(p.steps) && p.steps.length >= 2, 'Flow needs 2+ steps'); p.steps.forEach((s, i) => typeof s === 'string' || node(s, `Flow step ${i + 1}`)); },
  Stack: (p) => { need(Array.isArray(p.blocks) && p.blocks.length >= 1, 'Stack needs blocks'); p.blocks.forEach((b, i) => { node(b, `Stack block ${i + 1}`); need(num(b.tokens), `Stack block ${i + 1} needs numeric tokens`); }); },
  Trace: (p) => { need(Array.isArray(p.steps) && p.steps.length >= 2, 'Trace needs 2+ steps'); p.steps.forEach((s, i) => { need(ROLES.has(s.role), `Trace step ${i + 1}: unknown role ${s.role}`); need(typeof s.text === 'string', `Trace step ${i + 1} needs text`); }); },
  Compare: (p) => { need(Array.isArray(p.cols) && p.cols.length >= 2 && p.cols.length <= 4, 'Compare needs 2-4 cols'); p.cols.forEach((c, i) => { need(typeof c.title === 'string', `Compare col ${i + 1} needs a title`); need(KINDS.has(c.kind), `Compare col ${i + 1}: bad kind`); need(Array.isArray(c.rows) && c.rows.length >= 1, `Compare col ${i + 1} needs rows`); }); },
  Bars: (p) => { need(Array.isArray(p.bars) && p.bars.length >= 2, 'Bars needs 2+ bars'); p.bars.forEach((b, i) => { node(b, `Bar ${i + 1}`); need(num(b.value) && b.value >= 0, `Bar ${i + 1} needs a value >= 0`); }); },
  Lanes: (p) => {
    need(Array.isArray(p.lanes) && p.lanes.some((l) => !l.heading), 'Lanes needs lanes');
    const total = p.total ?? Math.max(...p.lanes.map((l) => l.end ?? 0));
    p.lanes.forEach((l, i) => { if (l.heading) return; need(typeof l.label === 'string', `Lane ${i + 1} needs a label`); need(num(l.start) && num(l.end) && l.end > l.start, `Lane ${i + 1} needs start < end`); need(l.end <= total, `Lane ${i + 1} ends after total`); need(KINDS.has(l.kind), `Lane ${i + 1}: bad kind`); });
  },
  Fan: (p) => { node(p.root, 'Fan root'); need(Array.isArray(p.items) && p.items.length >= 2 && p.items.length <= 6, 'Fan needs 2-6 items'); p.items.forEach((x, i) => node(x, `Fan item ${i + 1}`)); if (p.merge) node(p.merge, 'Fan merge'); if (p.pick !== undefined) need(p.pick >= 0 && p.pick < p.items.length, 'Fan pick out of range'); },
  States: (p) => {
    need(Array.isArray(p.states) && p.states.length >= 2 && p.states.length <= 6, 'States needs 2-6 states');
    const ids = new Set(p.states.map((s) => s.id));
    p.states.forEach((s, i) => { need(typeof s.id === 'string', `State ${i + 1} needs an id`); node(s, `State ${s.id}`); });
    need(Array.isArray(p.edges), 'States needs edges');
    p.edges.forEach((e) => need(ids.has(e.from) && ids.has(e.to), `States edge ${e.from}→${e.to} names an unknown state`));
    (p.path ?? []).forEach((id) => need(ids.has(id), `States path names unknown state ${id}`));
    (p.path ?? []).slice(1).forEach((id, k) => need(p.edges.some((e) => e.from === p.path[k] && e.to === id), `States path hop ${p.path[k]}→${id} has no edge`));
  },
};
const components = Object.fromEntries(Object.entries(CHECKS).map(([name, check]) => [name, (props) => { try { check(props); } catch (e) { throw new Error(`<${name}>: ${e.message}`); } return null; }]));
export const FIGURES = Object.keys(CHECKS).filter((n) => n !== 'Callout');

let bad = 0;
const fail = (f, msg) => { bad++; console.log(`✗ ${f}: ${msg}`); };
const dir = path.join(ROOT, 'src/content/lessons');
for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.mdx')).sort()) {
  const slug = file.replace(/\.mdx$/, '');
  if (only.size && !only.has(slug)) continue;
  const src = fs.readFileSync(path.join(dir, file), 'utf8');
  const m = src.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) { fail(file, 'no frontmatter'); continue; }
  let fm;
  try { fm = yaml.load(m[1]); } catch (e) { fail(file, 'YAML: ' + e.message); continue; }
  const r = lesson.safeParse(fm);
  if (!r.success) { fail(file, r.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')); continue; }
  const d = r.data;
  const cur = curriculum.find((c) => c.slug === slug);
  if (!cur) fail(file, 'slug not in curriculum');
  else {
    if (cur.order !== d.order) fail(file, `order ${d.order} should be ${cur.order}`);
    if (cur.section !== d.section) fail(file, `section ${d.section} should be ${cur.section}`);
  }
  d.quiz.forEach((q, i) => { if (q.answer >= q.options.length) fail(file, `quiz ${i + 1} answer out of range`); });
  const id = d.build.scenario ?? slug;
  if (d.build.type === 'lab' && !fs.existsSync(path.join(ROOT, 'src/content/scenarios', id + '.json'))) fail(file, `missing scenario ${id}.json`);
  if (d.build.type === 'code') {
    for (const f of ['starter.py', 'solution.py', 'check.py'])
      if (!fs.existsSync(path.join(ROOT, 'src/content/codelabs', id, f))) fail(file, `missing codelab ${id}/${f}`);
    if (!['README.md', 'README.mdx'].some((f) => fs.existsSync(path.join(ROOT, 'src/content/codelabs', id, f)))) fail(file, `missing codelab ${id}/README.md(x)`);
  }
  try {
    await compile(m[2]);
    const { default: Content } = await evaluate(m[2], { ...runtime });
    const { renderToStaticMarkup } = await import('react-dom/server');
    renderToStaticMarkup(runtime.jsx(Content, { components }));
  } catch (e) { fail(file, 'MDX: ' + (e.reason || e.message) + (e.line ? ` (body line ${e.line})` : '')); }
  for (const [, s] of m[2].matchAll(/\]\(\/c\/([a-z_]+)\/(?:build\/)?\)/g)) if (!slugs.has(s)) fail(file, `link to unknown lesson /c/${s}/`);
  const h2 = (m[2].match(/^## /gm) || []).length;
  if (h2 < 4 || h2 > 6) fail(file, `${h2} H2 sections (want 4-6)`);
  const words = m[2].replace(/```[\s\S]*?```/g, '').replace(new RegExp(`<(${FIGURES.join('|')})\\b[\\s\\S]*?\\/>`, 'g'), ' ').replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length;
  if (words < 550 || words > 1200) fail(file, `${words} words (want 600-1000)`);
  if (/^## .*—/m.test(m[2])) fail(file, 'em-dash in a heading');
  if (!bad) console.log(`✓ ${slug} (${words} words, ${h2} sections)`);
}
// Capstone parts and code lab READMEs: MDX and figure props only.
// node scripts/validate-content.mjs projects/nanoharness/02-tools.mdx codelabs/structured/README.mdx
const extra = [...only].filter((a) => a.includes('/'));
const extraFiles = only.size ? extra : [
  ...fs.readdirSync(path.join(ROOT, 'src/content/projects')).flatMap((p) => fs.readdirSync(path.join(ROOT, 'src/content/projects', p)).filter((f) => f.endsWith('.mdx')).map((f) => `projects/${p}/${f}`)),
  ...fs.readdirSync(path.join(ROOT, 'src/content/codelabs')).filter((c) => fs.existsSync(path.join(ROOT, 'src/content/codelabs', c, 'README.mdx'))).map((c) => `codelabs/${c}/README.mdx`),
];
for (const rel of extraFiles) {
  const before = bad;
  const src = fs.readFileSync(path.join(ROOT, 'src/content', rel), 'utf8');
  // Imports (e.g. SITE on the overview pages) are stubbed: this check is about the figures.
  const stubs = [...src.matchAll(/^import \{([^}]+)\} from .*$/gm)].flatMap((m) => m[1].split(',').map((x) => x.trim()).filter(Boolean));
  const body = stubs.map((n) => `export const ${n} = new Proxy({}, { get: () => 'x' });`).join('\n') + '\n\n' + src.replace(/^---\n[\s\S]*?\n---\n/, '').replace(/^import .*$/gm, '');
  try {
    const { default: Content } = await evaluate(body, { ...runtime });
    const { renderToStaticMarkup } = await import('react-dom/server');
    renderToStaticMarkup(runtime.jsx(Content, { components }));
  } catch (e) { fail(rel, 'MDX: ' + (e.reason || e.message) + (e.line ? ` (body line ${e.line})` : '')); }
  if (bad === before) console.log(`✓ ${rel}`);
}

console.log(bad ? `${bad} problem(s)` : 'all good');
process.exit(bad ? 1 : 0);
