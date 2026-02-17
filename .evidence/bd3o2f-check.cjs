const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 980 } });
  const page = await context.newPage();

  const modes = ['native', 'companion', 'both'];
  const results = [];

  for (const mode of modes) {
    await page.goto(`http://127.0.0.1:5180/?agent_mode=${mode}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);

    const terminalCount = await page.locator('[data-testid="terminal-panel"], [data-testid="terminal-panel-collapsed"]').count();
    const companionCount = await page.locator('[data-testid="companion-panel"], [data-testid="companion-panel-collapsed"]').count();
    const railLocator = mode === 'companion'
      ? page.locator('[data-testid="companion-panel"], [data-testid="companion-panel-collapsed"]').first()
      : page.locator('[data-testid="terminal-panel"], [data-testid="terminal-panel-collapsed"]').first();
    const railBox = await railLocator.boundingBox().catch(() => null);
    const viewport = page.viewportSize();
    const reachesBottom = !!(railBox && viewport && (railBox.y + railBox.height) >= (viewport.height - 4));
    results.push({ mode, terminalCount, companionCount, reachesBottom });
  }

  await page.goto('http://127.0.0.1:5180/?agent_mode=native', { waitUntil: 'networkidle' });
  const wsCheck = await page.evaluate(async () => {
    const portNumber = Number.parseInt(window.location.port, 10);
    const isDevPort = Number.isFinite(portNumber)
      && ((portNumber >= 3000 && portNumber <= 3010)
      || (portNumber >= 4173 && portNumber <= 4179)
      || (portNumber >= 5173 && portNumber <= 5199));
    const apiBase = isDevPort
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : window.location.origin;
    const wsBase = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${new URL(apiBase).host}`;

    const check = (url) => new Promise((resolve) => {
      const ws = new WebSocket(url);
      const t = setTimeout(() => resolve({ url, status: 'timeout' }), 4000);
      ws.onopen = () => {
        clearTimeout(t);
        ws.close();
        resolve({ url, status: 'open' });
      };
      ws.onerror = () => {
        clearTimeout(t);
        resolve({ url, status: 'error' });
      };
      ws.onclose = (e) => {
        if (e.code !== 1000) {
          clearTimeout(t);
          resolve({ url, status: `close:${e.code}` });
        }
      };
    });

    const pty = await check(`${wsBase}/ws/pty?provider=shell`);
    const stream = await check(`${wsBase}/ws/claude-stream?mode=ask`);
    return { wsBase, pty, stream };
  });

  console.log(JSON.stringify({ results, wsCheck }, null, 2));
  await browser.close();
})();
