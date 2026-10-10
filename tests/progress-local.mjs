// Progress survives a local run: dev server restart and browser restart, for lessons, labs and capstone parts.
// CHROMIUM=/path/to/chrome node tests/progress-local.mjs   (starts and stops `astro dev` itself; port 4321 must be free)
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = 'http://localhost:4321';
const fails = [];
const ok = (cond, msg) => { console.log(`${cond ? '✓' : '✗'} ${msg}`); if (!cond) fails.push(msg); };

async function startDev() {
  const p = spawn('npx', ['astro', 'dev', '--port', '4321'], { stdio: ['ignore', 'pipe', 'pipe'], detached: true });
  let out = '';
  await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`dev server did not start:\n${out}`)), 90000);
    const onData = (d) => { out += d; if (out.includes('localhost:4321')) { clearTimeout(t); resolve(); } };
    p.stdout.on('data', onData);
    p.stderr.on('data', onData);
    p.on('exit', (code) => { clearTimeout(t); reject(new Error(`dev server exited (${code}):\n${out}`)); });
  });
  return p;
}
const stop = (p) => { p.removeAllListeners('exit'); try { process.kill(-p.pid); } catch { /* already gone */ } };
const profile = await mkdtemp(join(tmpdir(), 'fah-profile-'));
const open = () => chromium.launchPersistentContext(profile, { executablePath: process.env.CHROMIUM || undefined });

let dev = await startDev();
let ctx = await open();
let page = ctx.pages()[0] ?? await ctx.newPage();
await page.goto(BASE + '/c/tokens/#build', { waitUntil: 'networkidle' });
await page.locator('[data-complete-toggle]').click();
await page.goto(BASE + '/c/agent_loop/build/', { waitUntil: 'networkidle' });
await page.getByRole('button', { name: /Hint/ }).click();
await page.getByRole('button', { name: /Hint/ }).click();
await page.getByRole('button', { name: 'Show solution' }).click();
await page.waitForTimeout(300);
await page.getByRole('button', { name: /Run/ }).first().click();
await page.waitForSelector('.passed', { timeout: 10000 }).catch(() => {});
await page.goto(BASE + '/p/nanoharness/1/', { waitUntil: 'networkidle' });
await page.locator('[data-complete-toggle]').click();
await ctx.close();
stop(dev);
await new Promise((r) => setTimeout(r, 2000));

dev = await startDev();
ctx = await open();
page = ctx.pages()[0] ?? await ctx.newPage();
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
ok(await page.locator('[data-tick="tokens"].done').count() === 1, 'lesson marked complete survives restarts');
ok(await page.locator('[data-tick="agent_loop"].done').count() === 1, 'passing a lab marks the lesson complete and survives restarts');
ok((await page.locator('[data-progress-count]').innerText()).startsWith('2 of'), 'home shows "2 of N done"');
await page.goto(BASE + '/p/nanoharness/', { waitUntil: 'networkidle' });
ok(await page.locator('[data-tick="p:nanoharness/1"].done').count() === 1, 'capstone part marked complete survives restarts');
await ctx.close();
stop(dev);
console.log(fails.length ? `${fails.length} failure(s)` : 'all local progress checks passed');
process.exit(fails.length ? 1 : 0);
