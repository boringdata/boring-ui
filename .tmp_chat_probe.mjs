import { chromium } from 'playwright';
const browser = await chromium.launch({headless:true});
const page = await browser.newPage();
page.on('console', m=>{if(m.type()==='error') console.log('console-error', m.text())});
await page.goto('http://213.32.19.186:5173', {waitUntil:'networkidle', timeout:60000});
await page.waitForTimeout(2000);
const ta = page.locator('textarea').first();
await ta.click();
await ta.fill('Reply with exactly: UI chat ok');
await ta.press('Enter');
let got=false;
for (let i=0;i<30;i++) {
  const body = (await page.textContent('body'))||'';
  if (body.includes('UI chat ok')) { got=true; break; }
  await page.waitForTimeout(1000);
}
console.log('got', got);
await page.screenshot({path:'/tmp/chat_probe.png', fullPage:true});
await browser.close();
