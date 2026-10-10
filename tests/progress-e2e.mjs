// Browser test: export progress from one browser, import it into another.
// npm run build && npx astro preview & then: CHROMIUM=/path/to/chrome node tests/progress-e2e.mjs [baseUrl]
import { chromium } from 'playwright';
import { readFile } from 'node:fs/promises';
const BASE = process.argv[2] || 'http://localhost:4321';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const fails = [];
const ok = (cond, msg) => { console.log(`${cond ? '✓' : '✗'} ${msg}`); if (!cond) fails.push(msg); };

const a = await browser.newContext({ acceptDownloads: true });
const pa = await a.newPage();
const errors = []; pa.on('pageerror', (e) => errors.push(String(e)));
await pa.goto(BASE + '/c/llm/', { waitUntil: 'networkidle' });
await pa.locator('[data-complete-toggle]').click();
await pa.evaluate(() => localStorage.setItem('fah-code-demo', 'print("hi")'));
await pa.goto(BASE + '/progress/', { waitUntil: 'networkidle' });
ok((await pa.locator('#progress-summary').innerText()).includes('1 completed item'), 'summary counts completed lessons');
const [download] = await Promise.all([pa.waitForEvent('download'), pa.getByRole('button', { name: 'Download progress file' }).click()]);
const path = await download.path();
const file = JSON.parse(await readFile(path, 'utf8'));
ok(file.format === 'free-agent-harness-progress' && file.data['fah-code-demo'] === 'print("hi")', 'export file has progress and code');

const b = await browser.newContext();
const pb = await b.newPage();
pb.on('pageerror', (e) => errors.push(String(e)));
await pb.goto(BASE + '/c/tokens/', { waitUntil: 'networkidle' });
await pb.locator('[data-complete-toggle]').click();
await pb.goto(BASE + '/progress/', { waitUntil: 'networkidle' });
await pb.locator('#import-progress').setInputFiles(path);
await pb.waitForTimeout(300);
ok((await pb.locator('#transfer-note').innerText()).includes('2 completed items'), 'import merges with existing progress');
await pb.goto(BASE + '/c/llm/', { waitUntil: 'networkidle' });
ok((await pb.locator('[data-complete-toggle]').innerText()).includes('Completed'), 'imported lesson shows as completed');
await pb.goto(BASE + '/progress/', { waitUntil: 'networkidle' });
await pb.locator('#import-progress').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{"hello":1}') });
await pb.waitForTimeout(300);
ok((await pb.locator('#transfer-note').getAttribute('class')) === 'bad', 'a wrong file is rejected with a message');
ok(errors.length === 0, `no page errors ${errors.join(' | ')}`);
await browser.close();
console.log(fails.length ? `${fails.length} failure(s)` : 'all progress checks passed');
process.exit(fails.length ? 1 : 0);
