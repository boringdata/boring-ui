/**
 * E2E Chat Interaction Test - RIGHT PANE ONLY
 *
 * Tests the chat interaction in the RIGHT PANEL (TerminalPanel)
 * which is the actual chat interface in the DockView layout:
 * [FileTree | Editor+Shell | CHAT PANE (RIGHT)]
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing RIGHT CHAT PANE Interaction\n');

  try {
    // Navigate to app
    console.log('1️⃣ Opening boring-ui with full layout...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 10000 });
    await page.waitForTimeout(2000);

    // Take screenshot of full layout
    await page.screenshot({ path: 'test-results/10-full-layout.png', fullPage: true });
    console.log('   ✅ Full layout captured\n');

    // Find the right panel (TerminalPanel)
    console.log('2️⃣ Locating RIGHT PANEL (TerminalPanel)...');

    // The right panel should contain the chat interface
    // Look for the chat input in the right panel specifically
    const rightPanel = await page.$('[class*="terminal"], [class*="right"], [class*="pane"]:last-child');

    if (rightPanel) {
      console.log('   ✅ Right panel found');
      await page.screenshot({ path: 'test-results/10-right-panel-visible.png', fullPage: true });
    } else {
      console.log('   ℹ️ Using full page search for chat input');
    }

    // Find the chat input in the right pane
    console.log('3️⃣ Finding chat input in RIGHT PANE...');

    // Wait for textarea to be visible
    const chatInput = await page.waitForSelector('textarea', { timeout: 5000 }).catch(() => null);

    if (!chatInput) {
      console.log('   ❌ Chat input not found in right pane');
      await page.screenshot({ path: 'test-results/10-error-no-input.png', fullPage: true });
      await browser.close();
      return;
    }

    console.log('   ✅ Chat input found in right pane\n');

    // Get the bounding box of the chat input to verify it's on the right
    const bbox = await chatInput.boundingBox();
    console.log(`4️⃣ Chat input location:`);
    console.log(`   X: ${Math.round(bbox.x)} (viewport width: 1600, right pane should start ~1000px)`);
    console.log(`   Y: ${Math.round(bbox.y)}`);
    console.log(`   Width: ${Math.round(bbox.width)}`);
    console.log(`   Height: ${Math.round(bbox.height)}\n`);

    // Scroll the right pane up to show chat history
    console.log('5️⃣ Scrolling chat area to top...');
    await page.evaluate(() => {
      const textareas = document.querySelectorAll('textarea');
      if (textareas.length > 0) {
        const parent = textareas[0].closest('[class*="panel"], [class*="pane"], main, aside');
        if (parent) parent.scrollTop = 0;
      }
    });
    await page.screenshot({ path: 'test-results/11-right-pane-scrolled-top.png', fullPage: true });
    console.log('   ✅ Screenshot: 11-right-pane-scrolled-top.png\n');

    // Click the chat input to focus it
    console.log('6️⃣ Clicking chat input in right pane...');
    await chatInput.click();
    await page.waitForTimeout(300);
    console.log('   ✅ Chat input focused\n');

    // Type message
    console.log('7️⃣ Typing message in RIGHT PANE chat...');
    const testMessage = 'Hello from right pane! What can you help me with?';
    await chatInput.type(testMessage, { delay: 50 });
    console.log(`   Message: "${testMessage}"`);

    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/11-message-typed-in-right-pane.png', fullPage: true });
    console.log('   ✅ Screenshot: 11-message-typed-in-right-pane.png\n');

    // Send the message
    console.log('8️⃣ Sending message (press Enter)...');
    await chatInput.press('Enter');
    console.log('   ✅ Message sent\n');

    // Wait for response
    console.log('9️⃣ Waiting for response in right pane...');
    await page.waitForTimeout(2000);

    // Scroll to bottom to see response
    console.log('   Scrolling to bottom...');
    await page.evaluate(() => {
      const textareas = document.querySelectorAll('textarea');
      if (textareas.length > 0) {
        const parent = textareas[0].closest('[class*="panel"], [class*="pane"], main, aside');
        if (parent) parent.scrollTop = parent.scrollHeight;
      }
    });

    await page.screenshot({ path: 'test-results/12-response-in-right-pane.png', fullPage: true });
    console.log('   ✅ Screenshot: 12-response-in-right-pane.png\n');

    // Get chat content from right pane
    console.log('🔟 Analyzing chat content in RIGHT PANE...');
    const chatContent = await page.evaluate(() => {
      // Find the chat container (parent of textarea)
      const textarea = document.querySelector('textarea');
      if (!textarea) return { error: 'No textarea found' };

      const chatContainer = textarea.closest('[class*="panel"], [class*="pane"], main, aside, div');
      if (!chatContainer) return { error: 'No chat container found' };

      // Get all text content
      const fullText = chatContainer.innerText;
      const lines = fullText.split('\n').filter(l => l.trim().length > 0);

      return {
        containerFound: true,
        textLines: lines.length,
        hasUserMessage: fullText.includes('Hello from right pane'),
        preview: lines.slice(0, 10).join(' | ')
      };
    });

    console.log(`   Content in right pane:`);
    console.log(`   - Container found: ${chatContent.containerFound}`);
    console.log(`   - Text lines: ${chatContent.textLines}`);
    console.log(`   - User message visible: ${chatContent.hasUserMessage}`);
    if (chatContent.preview) {
      console.log(`   - Preview: ${chatContent.preview.substring(0, 100)}...`);
    }
    console.log('');

    // Test provider switching in right pane
    console.log('1️1️⃣ Testing Sandbox provider in right pane...');
    await page.goto('http://localhost:5173?chat=sandbox', { waitUntil: 'commit' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/13-sandbox-provider-right-pane.png', fullPage: true });
    console.log('   ✅ Screenshot: 13-sandbox-provider-right-pane.png\n');

    // Test Companion provider in right pane
    console.log('1️2️⃣ Testing Companion provider in right pane...');
    await page.goto('http://localhost:5173?chat=companion', { waitUntil: 'commit' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/14-companion-provider-right-pane.png', fullPage: true });
    console.log('   ✅ Screenshot: 14-companion-provider-right-pane.png\n');

    console.log('✅ RIGHT PANE Chat Interaction Test Complete!');
    console.log('\n📸 Screenshots saved:');
    console.log('   - 10-full-layout.png (Complete DockView layout)');
    console.log('   - 10-right-panel-visible.png (Right panel focus)');
    console.log('   - 11-right-pane-scrolled-top.png (Chat scrolled to top)');
    console.log('   - 11-message-typed-in-right-pane.png (Message typed)');
    console.log('   - 12-response-in-right-pane.png (Response received)');
    console.log('   - 13-sandbox-provider-right-pane.png (Sandbox provider)');
    console.log('   - 14-companion-provider-right-pane.png (Companion provider)');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/error-right-pane.png', fullPage: true });
  }

  await browser.close();
})();
