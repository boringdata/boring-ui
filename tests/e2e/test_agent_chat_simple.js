/**
 * E2E Agent Chat Simple Test - AGENT ONLY (No Shell)
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing AGENT CHAT (Shell Removed)\n');

  try {
    console.log('1️⃣ Opening app with agent chat only...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: 'test-results/30-agent-only-layout.png', fullPage: true });
    console.log('   ✅ Layout captured\n');

    // Find agent chat input
    console.log('2️⃣ Finding agent chat input...');
    const chatInput = await page.$('textarea');

    if (!chatInput) {
      console.log('   ❌ No textarea found');
      await page.screenshot({ path: 'test-results/30-error-no-input.png', fullPage: true });
      await browser.close();
      return;
    }

    console.log('   ✅ Agent chat input found\n');

    // Test 1: Type message
    console.log('3️⃣ Typing message to Agent...');
    await chatInput.click();
    await page.waitForTimeout(300);
    const msg1 = 'Hello! What is boring-ui?';
    await chatInput.type(msg1, { delay: 50 });
    console.log(`   Message: "${msg1}"`);

    await page.screenshot({ path: 'test-results/31-agent-message-typed.png', fullPage: true });
    console.log('   ✅ Screenshot saved\n');

    // Send message
    console.log('4️⃣ Sending message (Enter)...');
    await chatInput.press('Enter');
    console.log('   ✅ Sent\n');

    // Wait for response
    console.log('5️⃣ Waiting for Agent response...');
    await page.waitForTimeout(2500);

    await page.screenshot({ path: 'test-results/32-agent-response.png', fullPage: true });
    console.log('   ✅ Response captured\n');

    // Test provider switching
    console.log('6️⃣ Testing Sandbox provider...');
    await page.goto('http://localhost:5173?chat=sandbox', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'test-results/33-sandbox.png', fullPage: true });
    console.log('   ✅ Sandbox captured\n');

    console.log('✅ Agent Chat Test Complete!\n');
    console.log('📸 Screenshots:');
    console.log('   - 30-agent-only-layout.png');
    console.log('   - 31-agent-message-typed.png');
    console.log('   - 32-agent-response.png');
    console.log('   - 33-sandbox.png');

  } catch (error) {
    console.error('❌ Error:', error.message);
  }

  await browser.close();
})();
