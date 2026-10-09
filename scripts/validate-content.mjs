// Fast content check that does not need a full Astro build (safe to run in parallel).
// node scripts/validate-content.mjs [slug ...]
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import { compile } from '@mdx-js/mdx';
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
  if (d.build.type === 'code') for (const f of ['README.md', 'starter.py', 'solution.py', 'check.py'])
    if (!fs.existsSync(path.join(ROOT, 'src/content/codelabs', id, f))) fail(file, `missing codelab ${id}/${f}`);
  try { await compile(m[2]); } catch (e) { fail(file, 'MDX: ' + (e.reason || e.message) + (e.line ? ` (body line ${e.line})` : '')); }
  for (const [, s] of m[2].matchAll(/\]\(\/c\/([a-z_]+)\/(?:build\/)?\)/g)) if (!slugs.has(s)) fail(file, `link to unknown lesson /c/${s}/`);
  const h2 = (m[2].match(/^## /gm) || []).length;
  if (h2 < 4 || h2 > 6) fail(file, `${h2} H2 sections (want 4-6)`);
  const words = m[2].replace(/```[\s\S]*?```/g, '').replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length;
  if (words < 550 || words > 1200) fail(file, `${words} words (want 600-1000)`);
  if (/^## .*—/m.test(m[2])) fail(file, 'em-dash in a heading');
  if (!bad) console.log(`✓ ${slug} (${words} words, ${h2} sections)`);
}
console.log(bad ? `${bad} problem(s)` : 'all good');
process.exit(bad ? 1 : 0);
