// Browser smoke test against a running preview (npm run build && npx astro preview).
// CHROMIUM=/path/to/chrome node tests/e2e.mjs [baseUrl]
import { chromium } from 'playwright';
const BASE = process.argv[2] || 'http://localhost:4321';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const fails = [];
const ok = (cond, msg) => { console.log(`${cond ? '✓' : '✗'} ${msg}`); if (!cond) fails.push(msg); };

for (const width of [1280, 375]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  ok((await page.locator('.lesson-list li').count()) === 54, `[${width}] home lists 54 lessons`);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `[${width}] home has no horizontal scroll`);
  await page.getByRole('link', { name: /Start here/ }).click();
  await page.waitForLoadState('networkidle');
  ok(page.url().endsWith('/c/llm/'), `[${width}] Start here opens lesson 1`);
  await page.locator('a[rel=next]').first().click();
  await page.waitForLoadState('networkidle');
  ok(page.url().endsWith('/c/tokens/'), `[${width}] next link goes to lesson 2`);
  await page.locator('[data-complete-toggle]').click();
  ok((await page.locator('[data-complete-toggle]').innerText()).includes('Completed'), `[${width}] mark complete toggles`);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `[${width}] lesson has no horizontal scroll`);
  await page.goto(BASE + '/c/agent_loop/build/', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /Run/ }).first().click();
  await page.waitForTimeout(500);
  ok((await page.locator('.goals li.fail').count()) > 0, `[${width}] lab starter fails a goal`);
  await page.getByRole('button', { name: /Hint/ }).click();
  await page.getByRole('button', { name: /Hint/ }).click();
  await page.getByRole('button', { name: 'Show solution' }).click();
  await page.waitForTimeout(200);
  await page.getByRole('button', { name: /Run/ }).first().click();
  await page.waitForSelector('.passed', { timeout: 5000 }).catch(() => {});
  ok(await page.locator('.passed').isVisible(), `[${width}] lab solution passes`);
  ok(errors.length === 0, `[${width}] no page errors ${errors.join(' | ')}`);
  await page.close();
}
await browser.close();
console.log(fails.length ? `${fails.length} failure(s)` : 'all e2e checks passed');
process.exit(fails.length ? 1 : 0);
