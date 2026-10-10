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
  // Sub-lessons: one part at a time, Next walks through them, and the last step is "Build it".
  const parts = await page.locator('.steps-rail button').count();
  ok(parts >= 3, `[${width}] lesson is split into ${parts} parts`);
  ok((await page.locator('.lesson .step:visible').count()) === 1, `[${width}] only the current part is shown`);
  for (let i = 1; i < parts; i++) await page.locator('.step-nav .step-btn.next').click();
  ok(page.url().endsWith('#build') && (await page.locator('.lesson-after .build-cta .btn').isVisible()), `[${width}] Next ends on the Build it step`);
  ok((await page.locator('.lesson-after .step-btn.next').getAttribute('href'))?.includes('/c/'), `[${width}] Build it step links to the next lesson`);
  await page.locator('[data-complete-toggle]').click();
  ok((await page.locator('[data-complete-toggle]').innerText()).includes('Completed'), `[${width}] mark complete toggles`);
  await page.locator('.step-nav .step-btn.prev').click();
  ok((await page.locator('.lesson .step:visible').count()) === 1, `[${width}] Previous goes back a part`);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `[${width}] lesson has no horizontal scroll`);
  // Two-pane lesson: on wide screens the stage shows the figure for the part you are reading.
  await page.goto(BASE + '/c/agent_loop/', { waitUntil: 'networkidle' });
  if (width >= 1100) {
    ok(await page.locator('.stage').isVisible(), `[${width}] lesson stage is visible`);
    ok(!(await page.locator('.vis-inline').first().isVisible()), `[${width}] inline figures move to the stage`);
    await page.locator('.steps-rail button').nth(3).click(); // "Let us check the math" has several figures
    await page.waitForTimeout(900);
    const last = page.locator('.scrolly-text .step[data-current] .vis').last();
    await last.scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollBy(0, 200));
    await page.waitForTimeout(400);
    const n = Number(await last.getAttribute('data-frame')) + 1;
    ok((await page.locator('.stage .frame[data-active]').getAttribute('data-frame')) === String(n - 1), `[${width}] scrolling to the last figure shows it on the stage`);
    await page.locator('[data-stage-prev]').click();
    await page.waitForTimeout(900);
    ok((await page.locator('.stage .frame[data-active]').getAttribute('data-frame')) === String(n - 2), `[${width}] stage previous button steps back`);
  } else {
    ok(!(await page.locator('.stage').isVisible()), `[${width}] lesson stage is hidden on a phone`);
    ok(await page.locator('.vis-inline').first().isVisible(), `[${width}] figures stay inline on a phone`);
  }
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `[${width}] two-pane lesson has no horizontal scroll`);
  await page.goto(BASE + '/c/agent_loop/build/', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /Run/ }).first().click();
  await page.waitForSelector('.lab[data-state="done"]', { timeout: 10000 });
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
