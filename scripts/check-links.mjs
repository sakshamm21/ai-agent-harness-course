// Checks every internal href/src in dist/*.html resolves to a built file. Run after `npm run build`.
import fs from 'node:fs';
import path from 'node:path';
const DIST = path.resolve('dist');
const files = [];
(function walk(d) { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); fs.statSync(p).isDirectory() ? walk(p) : p.endsWith('.html') && files.push(p); } })(DIST);
let bad = 0;
const exists = (u) => {
  const clean = decodeURI(u.split('#')[0].split('?')[0]);
  if (!clean) return true;
  const p = path.join(DIST, clean);
  return fs.existsSync(p) && (fs.statSync(p).isFile() || fs.existsSync(path.join(p, 'index.html')));
};
for (const f of files) {
  const html = fs.readFileSync(f, 'utf8');
  for (const [, u] of html.matchAll(/(?:href|src)="(\/[^"]*)"/g)) {
    if (u.startsWith('//') || u.startsWith('/pagefind/')) continue;
    if (!exists(u)) { bad++; console.log(`✗ ${path.relative(DIST, f)} → ${u}`); }
  }
}
console.log(`${files.length} pages checked, ${bad} broken internal link(s)`);
process.exit(bad ? 1 : 0);
