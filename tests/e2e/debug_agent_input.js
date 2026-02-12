/**
 * Debug Script - Find the actual AGENT INPUT element
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🔍 Debugging Agent Chat Input Element\n');

  try {
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 15000 });
    await page.waitForTimeout(2000);

    // Deep DOM exploration
    const analysis = await page.evaluate(() => {
      const terminalPanel = document.querySelector('.terminal-panel-content');
      if (!terminalPanel) return { error: 'No terminal panel' };

      // Find all inputs
      const allInputs = terminalPanel.querySelectorAll('input, textarea, [contenteditable], [role="textbox"]');
      console.log(`Found ${allInputs.length} potential inputs`);

      const inputs = [];
      allInputs.forEach((el, i) => {
        const rect = el.getBoundingClientRect();
        inputs.push({
          index: i,
          type: el.tagName,
          role: el.getAttribute('role'),
          contenteditable: el.getAttribute('contenteditable'),
          placeholder: el.placeholder || el.getAttribute('aria-label'),
          className: el.className,
          position: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
        });
      });

      // Also check for divs with contenteditable or special classes
      const specialDivs = terminalPanel.querySelectorAll('[contenteditable="true"]');
      console.log(`Found ${specialDivs.length} contenteditable elements`);

      // Check the structure
      return {
        terminalPanelFound: true,
        terminalPanelClasses: terminalPanel.className,
        potentialInputs: inputs,
        contentEditableCount: specialDivs.length,
        firstContentEditableInfo: specialDivs.length > 0 ? {
          className: specialDivs[0].className,
          parentClassName: specialDivs[0].parentElement?.className,
          textContent: specialDivs[0].textContent?.substring(0, 100),
        } : null,
      };
    });

    console.log(JSON.stringify(analysis, null, 2));

  } catch (error) {
    console.error('Error:', error.message);
  }

  await browser.close();
})();
