// Loads every /c/<slug>/build/ page, runs the starter, loads the solution, runs again; reports page errors.
import { chromium } from 'playwright';
import fs from 'node:fs';
const BASE = process.argv[2] || 'http://localhost:4321';
const slugs = fs.readdirSync('dist/c').filter((s) => fs.existsSync(`dist/c/${s}/build/index.html`));
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
let bad = 0;
for (const s of slugs) {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('dialog', (d) => d.accept());
  await page.goto(`${BASE}/c/${s}/build/`, { waitUntil: 'networkidle' });
  let note = '';
  if (await page.locator('.lab-grid').count()) {
    await page.getByRole('button', { name: /Run/ }).first().click();
    await page.waitForSelector('.lab[data-state="done"]', { timeout: 10000 });
    const fail = await page.locator('.goals li.fail').count();
    await page.getByRole('button', { name: /Hint/ }).click();
    await page.getByRole('button', { name: /Hint/ }).click();
    await page.getByRole('button', { name: 'Show solution' }).click();
    await page.waitForTimeout(150);
    await page.getByRole('button', { name: /Run/ }).first().click();
    await page.waitForSelector('.lab[data-state="done"]', { timeout: 10000 });
    const passed = await page.locator('.passed').isVisible();
    note = `lab starterFails=${fail > 0} solutionPasses=${passed}`;
    if (!(fail > 0 && passed)) bad++;
  } else note = 'codelab page loaded';
  if (errors.length) bad++;
  console.log(`${errors.length ? '✗' : '✓'} ${s}: ${note} ${errors.join(' | ')}`);
  await page.close();
}
await browser.close();
console.log(bad ? `${bad} problem(s)` : `all ${slugs.length} build pages ok`);
process.exit(bad ? 1 : 0);
