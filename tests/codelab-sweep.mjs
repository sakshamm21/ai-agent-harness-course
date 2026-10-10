// For every code lab: Check on the starter should fail, Check on the solution should pass, in real Pyodide.
// Build with PUBLIC_PYODIDE_URL=/pyodide/ and copy node_modules/pyodide into dist/pyodide first (see DEPLOY.md).
import { chromium } from 'playwright';
import fs from 'node:fs';
const BASE = process.argv[2] || 'http://localhost:4321';
const labs = fs.readdirSync('src/content/codelabs');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on('dialog', (d) => d.accept());
let bad = 0;
for (const id of labs) {
  const slug = id;
  await page.goto(`${BASE}/c/${slug}/build/`, { waitUntil: 'networkidle' });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '✓ Check' }).click();
  await page.waitForFunction(() => !document.querySelector('.runbar .btn')?.hasAttribute('disabled') && (document.querySelector('.cl-checks') || document.querySelector('.cl-output')), null, { timeout: 120000 });
  const starterPassed = await page.locator('.passed').isVisible();
  await page.getByRole('button', { name: 'Show solution' }).click();
  await page.getByRole('button', { name: '✓ Check' }).click();
  await page.waitForSelector('.passed', { timeout: 60000 }).catch(() => {});
  const solPassed = await page.locator('.passed').isVisible();
  const ok = !starterPassed && solPassed;
  if (!ok) bad++;
  const fails = ok ? '' : await page.locator('.cl-checks, .cl-output').allInnerTexts();
  console.log(`${ok ? '✓' : '✗'} ${id}: starter ${starterPassed ? 'PASSED' : 'fails'}, solution ${solPassed ? 'passes' : 'FAILS'} ${fails}`);
}
await browser.close();
process.exit(bad ? 1 : 0);
