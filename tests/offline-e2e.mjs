// Everything works on a local run with the internet switched off: every request that isn't to the local
// server is blocked. Run against `npm start` (or `npm run dev`; search is skipped there since it needs a build).
// CHROMIUM=/path/to/chrome node tests/offline-e2e.mjs [baseUrl] [--no-search]
import { chromium } from 'playwright';
const BASE = process.argv.find((a) => a.startsWith('http')) || 'http://localhost:4321';
const SEARCH = !process.argv.includes('--no-search');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const ctx = await browser.newContext();
const blocked = [];
await ctx.route('**/*', (route) => {
  const host = new URL(route.request().url()).hostname;
  if (host === 'localhost' || host === '127.0.0.1') return route.continue();
  blocked.push(route.request().url());
  return route.abort('internetdisconnected');
});
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
const fails = [];
const ok = (cond, msg) => { console.log(`${cond ? '✓' : '✗'} ${msg}`); if (!cond) fails.push(msg); };

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
ok((await page.locator('.lesson-list li').count()) === 54, 'home lists 54 lessons');

await page.goto(BASE + '/c/agent_loop/', { waitUntil: 'networkidle' });
ok((await page.locator('.prose').first().innerText()).length > 500, 'a lesson renders');

await page.goto(BASE + '/glossary/', { waitUntil: 'networkidle' });
ok((await page.locator('main').innerText()).length > 500, 'glossary renders');

await page.goto(BASE + '/c/agent_loop/build/', { waitUntil: 'networkidle' });
await page.getByRole('button', { name: /Hint/ }).click();
await page.getByRole('button', { name: /Hint/ }).click();
await page.getByRole('button', { name: 'Show solution' }).click();
await page.waitForTimeout(300);
await page.getByRole('button', { name: /Run/ }).first().click();
await page.waitForSelector('.passed', { timeout: 10000 }).catch(() => {});
ok(await page.locator('.passed').isVisible(), 'Agent Lab solution passes');

await page.goto(BASE + '/c/tools/build/', { waitUntil: 'networkidle' });
page.on('dialog', (d) => d.accept());
await page.getByRole('button', { name: 'Show solution' }).click();
await page.getByRole('button', { name: '✓ Check' }).click();
await page.waitForSelector('.passed', { timeout: 120000 }).catch(() => {});
ok(await page.locator('.passed').isVisible(), 'code lab runs Python offline and the solution passes');

if (SEARCH) {
  await page.goto(BASE + '/search/', { waitUntil: 'networkidle' });
  await page.locator('input').first().fill('context window');
  await page.waitForTimeout(1500);
  ok((await page.locator('main a[href*="/c/"]').count()) > 0, 'search finds lessons');
}

await page.goto(BASE + '/p/nanoharness/1/', { waitUntil: 'networkidle' });
await page.locator('[data-complete-toggle]').click();
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
ok(await page.locator('[data-tick="agent_loop"].done').count() === 1 && await page.locator('[data-tick="tools"].done').count() === 1, 'passing labs ticks lessons on the home page');
await page.goto(BASE + '/p/nanoharness/', { waitUntil: 'networkidle' });
ok(await page.locator('[data-tick="p:nanoharness/1"].done').count() === 1, 'capstone progress shows');

ok(errors.length === 0, `no page errors ${errors.join(' | ')}`);
console.log(blocked.length ? `blocked (offline): ${[...new Set(blocked.map((u) => new URL(u).host))].join(', ')}` : 'no requests left the machine');
await browser.close();
console.log(fails.length ? `${fails.length} failure(s)` : 'all offline checks passed');
process.exit(fails.length ? 1 : 0);
