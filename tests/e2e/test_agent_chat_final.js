/**
 * E2E Test - CORRECT AGENT CHAT INPUT
 *
 * Tests the React agent chat TEXTAREA on the RIGHT PANEL
 * Selector: textarea[placeholder="Reply..."]
 * Position: x~1225, y~786 (RIGHT SIDE)
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing AGENT CHAT - Correct Input on RIGHT PANE\n');

  try {
    console.log('1️⃣ Opening app...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: 'test-results/50-agent-chat-layout.png', fullPage: true });
    console.log('   ✅ Layout captured\n');

    // Find the CORRECT agent chat input
    console.log('2️⃣ Finding agent chat textarea...');
    const agentInput = await page.$('textarea[placeholder="Reply..."]');

    if (!agentInput) {
      console.log('   ❌ Agent chat textarea not found');
      await page.screenshot({ path: 'test-results/50-error.png', fullPage: true });
      await browser.close();
      return;
    }

    const bbox = await agentInput.boundingBox();
    console.log(`   ✅ Found textarea at x=${Math.round(bbox.x)}, y=${Math.round(bbox.y)}`);
    console.log(`   ✅ Size: ${Math.round(bbox.width)}x${Math.round(bbox.height)}\n`);

    // Click to focus
    console.log('3️⃣ Clicking agent chat input to focus...');
    await agentInput.click();
    await page.waitForTimeout(300);
    console.log('   ✅ Focused\n');

    // Type message
    console.log('4️⃣ Typing message to agent...');
    const msg1 = 'Hello Claude! What can you do?';
    await agentInput.type(msg1, { delay: 30 });
    console.log(`   Message: "${msg1}"`);

    await page.screenshot({ path: 'test-results/51-agent-message-typed.png', fullPage: true });
    console.log('   ✅ Screenshot: 51-agent-message-typed.png\n');

    // Send message
    console.log('5️⃣ Sending message (press Enter)...');
    await agentInput.press('Enter');
    console.log('   ✅ Message sent\n');

    // Wait for response
    console.log('6️⃣ Waiting for agent response...');
    await page.waitForTimeout(3000);

    await page.screenshot({ path: 'test-results/52-agent-response.png', fullPage: true });
    console.log('   ✅ Screenshot: 52-agent-response.png\n');

    // Find fresh input for second message
    console.log('7️⃣ Testing multi-turn conversation...');
    const agentInput2 = await page.$('textarea[placeholder="Reply..."]');

    if (agentInput2) {
      await agentInput2.click();
      await page.waitForTimeout(300);

      const msg2 = 'Can you help me test this app?';
      await agentInput2.type(msg2, { delay: 30 });
      console.log(`   Message 2: "${msg2}"`);

      await page.screenshot({ path: 'test-results/53-agent-message-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 53-agent-message-2.png');

      await agentInput2.press('Enter');
      console.log('   ✅ Message 2 sent\n');

      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/54-agent-response-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 54-agent-response-2.png\n');
    }

    console.log('✅ AGENT CHAT TEST COMPLETE!');
    console.log('\n📸 Screenshots captured:');
    console.log('   - 50-agent-chat-layout.png (Full layout with agent chat)');
    console.log('   - 51-agent-message-typed.png (Message typed in agent input)');
    console.log('   - 52-agent-response.png (Agent responding)');
    console.log('   - 53-agent-message-2.png (Second message)');
    console.log('   - 54-agent-response-2.png (Agent responds to 2nd message)');
    console.log('\n✅ This is the CORRECT agent chat on the RIGHT pane!');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/error-final.png', fullPage: true });
  }

  await browser.close();
})();
