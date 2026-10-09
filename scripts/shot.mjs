// node scripts/shot.mjs <path> <out.png> [width] [action]
import { chromium } from 'playwright';
const [, , path = '/', out = 'shot.png', width = '1280', action = ''] = process.argv;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: Number(width), height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto('http://localhost:4321' + path, { waitUntil: 'networkidle' });
if (action === 'run') { await page.getByRole('button', { name: /Run/ }).first().click(); await page.waitForTimeout(800); }
if (action === 'solution') {
  await page.getByRole('button', { name: /Hint/ }).click(); await page.getByRole('button', { name: /Hint/ }).click();
  await page.getByRole('button', { name: 'Show solution' }).click(); await page.waitForTimeout(300);
  await page.getByRole('button', { name: /Run/ }).first().click(); await page.waitForTimeout(800);
}
await page.screenshot({ path: out, fullPage: true });
console.log('errors:', errors.length ? errors.join('\n') : 'none');
await browser.close();
