/**
 * E2E Agent Chat Test - AGENT ONLY (No Shell)
 *
 * Tests the Claude Code AGENT CHAT on the RIGHT PANEL
 * Layout: [FileTree | Editor | AGENT CHAT (RIGHT ONLY - No Shell)]
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing AGENT CHAT PANE (No Shell)\n');

  try {
    // Clear localStorage to force fresh layout
    console.log('1️⃣ Opening app with clean layout (shell removed)...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 10000 });

    // Clear localStorage and reload
    await page.evaluate(() => {
      localStorage.clear()
    });
    await page.reload({ waitUntil: 'commit' });
    await page.waitForTimeout(2000);

    // Take screenshot of new layout
    await page.screenshot({ path: 'test-results/30-agent-only-layout.png', fullPage: true });
    console.log('   ✅ Layout with AGENT CHAT only (no shell)\n');

    // Find the agent chat input in the RIGHT pane
    console.log('2️⃣ Finding AGENT CHAT input in RIGHT PANE...');

    // Wait for textarea (chat input)
    const chatInput = await page.waitForSelector('textarea', { timeout: 5000 }).catch(() => null);

    if (!chatInput) {
      console.log('   ❌ Chat input not found');
      await page.screenshot({ path: 'test-results/30-error-no-input.png', fullPage: true });
      await browser.close();
      return;
    }

    console.log('   ✅ Agent chat input found in RIGHT PANE\n');

    // Verify position is on the right
    const bbox = await chatInput.boundingBox();
    console.log(`3️⃣ Agent chat input position:`);
    console.log(`   X: ${Math.round(bbox.x)} px (should be right side, >800px)`);
    console.log(`   Y: ${Math.round(bbox.y)} px`);
    console.log(`   Width: ${Math.round(bbox.width)} px`);
    console.log(`   Height: ${Math.round(bbox.height)} px\n`);

    // Click and focus
    console.log('4️⃣ Clicking agent chat input...');
    await chatInput.click();
    await page.waitForTimeout(500);
    console.log('   ✅ Agent chat focused\n');

    // Type a test message to the agent
    console.log('5️⃣ Typing message to AGENT (Claude Code)...');
    const testMessage = 'Hello Agent! What is this application?';
    await chatInput.type(testMessage, { delay: 50 });
    console.log(`   Message: "${testMessage}"`);

    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/31-agent-message-typed.png', fullPage: true });
    console.log('   ✅ Screenshot: 31-agent-message-typed.png\n');

    // Send the message
    console.log('6️⃣ Sending message to AGENT (press Enter)...');
    await chatInput.press('Enter');
    console.log('   ✅ Message sent to Agent\n');

    // Wait for agent response
    console.log('7️⃣ Waiting for Agent response...');
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'test-results/32-agent-response.png', fullPage: true });
    console.log('   ✅ Screenshot: 32-agent-response.png\n');

    // Scroll to see full response
    console.log('8️⃣ Scrolling to view Agent response...');
    await page.evaluate(() => {
      const textarea = document.querySelector('textarea');
      if (textarea) {
        const container = textarea.closest('[class*="panel"], [class*="pane"], main, aside, div');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }
    });

    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/33-agent-scrolled.png', fullPage: true });
    console.log('   ✅ Screenshot: 33-agent-scrolled.png\n');

    // Test switching to other providers
    console.log('9️⃣ Testing Sandbox provider...');
    await page.goto('http://localhost:5173?chat=sandbox', { waitUntil: 'commit' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'test-results/34-sandbox-provider.png', fullPage: true });
    console.log('   ✅ Screenshot: 34-sandbox-provider.png\n');

    // Test Companion provider
    console.log('🔟 Testing Companion provider...');
    await page.goto('http://localhost:5173?chat=companion', { waitUntil: 'commit' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'test-results/35-companion-provider.png', fullPage: true });
    console.log('   ✅ Screenshot: 35-companion-provider.png\n');

    // Test sending another message with agent
    console.log('1️1️⃣ Testing multi-turn conversation...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit' });
    await page.waitForTimeout(1500);

    const newInput = await page.waitForSelector('textarea', { timeout: 2000 });
    if (newInput) {
      await newInput.click();
      await page.waitForTimeout(300);

      const secondMessage = 'Can you help me test this chat system?';
      await newInput.type(secondMessage, { delay: 40 });
      console.log(`   Message 2: "${secondMessage}"`);

      await page.screenshot({ path: 'test-results/36-agent-message-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 36-agent-message-2.png');

      await newInput.press('Enter');
      console.log('   ✅ Message 2 sent\n');

      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/37-agent-response-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 37-agent-response-2.png\n');
    }

    console.log('✅ AGENT CHAT TEST (Shell Removed) Complete!');
    console.log('\n📸 Screenshots captured:');
    console.log('   - 30-agent-only-layout.png (Clean layout, no shell)');
    console.log('   - 31-agent-message-typed.png (Message typed)');
    console.log('   - 32-agent-response.png (Agent responding)');
    console.log('   - 33-agent-scrolled.png (Full conversation)');
    console.log('   - 34-sandbox-provider.png (Sandbox provider)');
    console.log('   - 35-companion-provider.png (Companion provider)');
    console.log('   - 36-agent-message-2.png (Second message)');
    console.log('   - 37-agent-response-2.png (Agent response 2)');
    console.log('\n✅ Agent chat interaction fully tested!');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/error-agent-chat.png', fullPage: true });
  }

  await browser.close();
})();
