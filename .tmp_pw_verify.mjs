import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];

page.on('console', (msg) => {
  const t = msg.type();
  if (t === 'error' || t === 'warning') errors.push(`[console:${t}] ${msg.text()}`);
});
page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));
page.on('requestfailed', (req) => errors.push(`[requestfailed] ${req.url()} :: ${req.failure()?.errorText}`));

await page.goto('http://213.32.19.186:5173', { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(2500);

const body = (await page.textContent('body')) || '';
const hasWarning = body.includes('Some features are unavailable');
const caps = await page.evaluate(async () => {
  try {
    const r = await fetch('/api/capabilities');
    return { status: r.status, json: await r.json() };
  } catch (e) {
    return { error: String(e) };
  }
});

console.log('hasFeatureWarning', hasWarning);
console.log('capabilitiesFetch', JSON.stringify(caps));
console.log('errorCount', errors.length);
for (const e of errors.slice(0, 30)) console.log(e);

await page.screenshot({ path: '/tmp/boring_ui_verify.png', fullPage: true });
await browser.close();
