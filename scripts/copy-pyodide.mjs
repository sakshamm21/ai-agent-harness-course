// Copy the Pyodide runtime from node_modules into public/pyodide/ so code labs run Python without a CDN
// (and without internet). Runs on `npm install` and before `dev`/`build`; cheap when already up to date.
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(root, 'node_modules', 'pyodide');
const dest = join(root, 'public', 'pyodide');
const FILES = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];

if (!existsSync(join(src, 'package.json'))) {
  console.warn('copy-pyodide: node_modules/pyodide is missing; code labs will fall back to jsDelivr. Run npm install.');
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
let copied = 0;
for (const f of FILES) {
  const from = join(src, f), to = join(dest, f);
  if (existsSync(to) && statSync(to).size === statSync(from).size && statSync(to).mtimeMs >= statSync(from).mtimeMs) continue;
  copyFileSync(from, to);
  copied++;
}
const { version } = JSON.parse(readFileSync(join(src, 'package.json'), 'utf8'));
if (copied) console.log(`copy-pyodide: copied Pyodide ${version} into public/pyodide/`);
