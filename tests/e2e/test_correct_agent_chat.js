/**
 * E2E Test - CORRECT AGENT CHAT INPUT on RIGHT PANE
 *
 * Tests the React agent chat component on the RIGHT panel,
 * NOT the shell textarea on the left.
 *
 * Layout: [FileTree | Editor | AGENT CHAT (RIGHT)]
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing AGENT CHAT (Right Pane) - NOT Shell\n');

  try {
    console.log('1️⃣ Opening app...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 15000 });
    await page.waitForTimeout(2000);

    // Screenshot of full layout
    await page.screenshot({ path: 'test-results/40-correct-layout.png', fullPage: true });
    console.log('   ✅ Layout captured\n');

    // Find the AGENT CHAT input specifically
    // The agent chat is rendered by assistant-ui, typically a contenteditable or similar
    // We need to find it in the RIGHT panel (terminal-panel-content)

    console.log('2️⃣ Finding AGENT CHAT input in RIGHT PANEL...');

    // Strategy: Find input/contenteditable in the terminal-panel-content (RIGHT)
    const agentChatInput = await page.waitForSelector(
      '.terminal-panel-content [contenteditable="true"], .terminal-panel-content input[type="text"], .terminal-panel-content textarea',
      { timeout: 5000 }
    ).catch(() => null);

    if (!agentChatInput) {
      console.log('   ℹ️ Exploring DOM to find agent chat input...');

      // Debug: Let's see what's in the terminal panel
      const terminalContent = await page.evaluate(() => {
        const panel = document.querySelector('.terminal-panel-content');
        if (!panel) return { error: 'No terminal panel found' };

        return {
          html: panel.innerHTML.substring(0, 500),
          hasContentEditable: !!panel.querySelector('[contenteditable]'),
          hasInput: !!panel.querySelector('input'),
          hasTextarea: !!panel.querySelector('textarea'),
          children: panel.childNodes.length,
          classes: panel.className,
        };
      });

      console.log('   Terminal panel info:', terminalContent);

      if (!terminalContent.error && terminalContent.hasContentEditable) {
        console.log('   ✅ Found contenteditable in terminal panel\n');
      } else {
        console.log('   ⚠️ Could not find typical input elements\n');
      }
    } else {
      console.log('   ✅ Found agent chat input\n');
    }

    // Try different selectors for the agent input
    console.log('3️⃣ Testing various agent chat input selectors...');

    const selectors = [
      '[contenteditable="true"]',  // Assistant-ui typically uses contenteditable
      '.terminal-panel-content [contenteditable]',
      '[role="textbox"]',
      '.chat-input',
      '.composer input',
      '.composer textarea',
    ];

    let foundInput = null;
    for (const selector of selectors) {
      const el = await page.$(selector);
      if (el) {
        const bbox = await el.boundingBox();
        if (bbox && bbox.x > 800) {  // Should be on right side (>800px in 1600px viewport)
          console.log(`   ✅ Found at selector: ${selector}`);
          console.log(`      Position: x=${Math.round(bbox.x)}, y=${Math.round(bbox.y)}`);
          foundInput = el;
          break;
        }
      }
    }

    if (!foundInput) {
      console.log('   ❌ Could not find agent chat input element');
      console.log('   Taking error screenshot...');
      await page.screenshot({ path: 'test-results/40-error-no-agent-input.png', fullPage: true });
      await browser.close();
      return;
    }

    // Found the input! Now test it
    console.log('\n4️⃣ Focusing agent chat input...');
    await foundInput.click();
    await page.waitForTimeout(500);
    console.log('   ✅ Input focused\n');

    // Type message
    console.log('5️⃣ Typing message to AGENT...');
    const testMsg = 'Hello Agent! What is this application?';

    // For contenteditable, we need to type differently
    await foundInput.focus();
    await page.keyboard.type(testMsg, { delay: 40 });
    console.log(`   Message: "${testMsg}"`);

    await page.screenshot({ path: 'test-results/41-agent-input-typed.png', fullPage: true });
    console.log('   ✅ Screenshot: 41-agent-input-typed.png\n');

    // Send message
    console.log('6️⃣ Sending message (Ctrl+Enter or Enter)...');
    // Try Enter first
    await page.keyboard.press('Enter');
    console.log('   ✅ Sent\n');

    // Wait for response
    console.log('7️⃣ Waiting for agent response...');
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'test-results/42-agent-response.png', fullPage: true });
    console.log('   ✅ Screenshot: 42-agent-response.png\n');

    console.log('✅ AGENT CHAT TEST COMPLETE!');
    console.log('\n📸 Screenshots:');
    console.log('   - 40-correct-layout.png');
    console.log('   - 41-agent-input-typed.png');
    console.log('   - 42-agent-response.png');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/error-agent-chat.png', fullPage: true });
  }

  await browser.close();
})();
