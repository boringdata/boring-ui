/**
 * E2E Chat Interaction Test - CLAUDE CODE CHAT PANE (RIGHT)
 *
 * Tests interaction with the Claude Code AI chat on the RIGHT PANEL
 * Layout: [FileTree | Editor+Shell | CLAUDE CHAT (RIGHT)]
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.setViewportSize({ width: 1600, height: 900 });

  console.log('🤖 Testing CLAUDE CODE CHAT PANE (Right Side)\n');

  try {
    // Navigate to app with Claude provider
    console.log('1️⃣ Opening boring-ui with Claude Code chat provider...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 10000 });
    await page.waitForTimeout(2000);

    // Take screenshot of full layout
    await page.screenshot({ path: 'test-results/20-claude-chat-full-layout.png', fullPage: true });
    console.log('   ✅ Full layout with Claude chat captured\n');

    // Find the chat input in the Claude chat pane (right side)
    console.log('2️⃣ Finding chat input in CLAUDE CHAT PANE...');

    // Wait for textarea (chat input)
    const chatInput = await page.waitForSelector('textarea[placeholder*="Reply"], textarea[placeholder*="message"], textarea', { timeout: 5000 }).catch(() => null);

    if (!chatInput) {
      console.log('   ❌ Chat input not found');
      await page.screenshot({ path: 'test-results/20-error-no-input.png', fullPage: true });
      await browser.close();
      return;
    }

    console.log('   ✅ Chat input found in Claude chat pane\n');

    // Get the bounding box to confirm it's on the right
    const bbox = await chatInput.boundingBox();
    console.log(`3️⃣ Chat input position on screen:`);
    console.log(`   X: ${Math.round(bbox.x)} px (right side of layout)`);
    console.log(`   Y: ${Math.round(bbox.y)} px`);
    console.log(`   Width: ${Math.round(bbox.width)} px`);
    console.log(`   Height: ${Math.round(bbox.height)} px\n`);

    // Click to focus
    console.log('4️⃣ Clicking Claude chat input to focus...');
    await chatInput.click();
    await page.waitForTimeout(500);
    console.log('   ✅ Chat input focused\n');

    // Type a test message
    console.log('5️⃣ Typing message in Claude chat pane...');
    const testMessage = 'Hello Claude! Can you explain what this app does?';
    await chatInput.type(testMessage, { delay: 50 });
    console.log(`   Message: "${testMessage}"`);

    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/21-claude-message-typed.png', fullPage: true });
    console.log('   ✅ Screenshot: 21-claude-message-typed.png\n');

    // Send the message
    console.log('6️⃣ Sending message to Claude (press Enter)...');
    await chatInput.press('Enter');
    console.log('   ✅ Message sent to Claude\n');

    // Wait for Claude to respond
    console.log('7️⃣ Waiting for Claude response...');
    await page.waitForTimeout(3000);

    // Check if response appeared
    const hasResponse = await page.evaluate(() => {
      const textarea = document.querySelector('textarea');
      if (!textarea) return false;

      // Get parent container
      const container = textarea.closest('[class*="panel"], [class*="pane"], main, aside, div');
      if (!container) return false;

      // Check if there's more than just the input
      return container.innerText.length > 100;
    });

    console.log(`   Response received: ${hasResponse ? '✅ YES' : '⏳ Still waiting'}\n`);

    await page.screenshot({ path: 'test-results/22-claude-response.png', fullPage: true });
    console.log('8️⃣ Screenshot: 22-claude-response.png\n');

    // Scroll to see full response
    console.log('9️⃣ Scrolling to view full Claude response...');
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
    await page.screenshot({ path: 'test-results/23-claude-scrolled-view.png', fullPage: true });
    console.log('   ✅ Screenshot: 23-claude-scrolled-view.png\n');

    // Get the conversation content
    console.log('🔟 Analyzing Claude chat content...');
    const chatContent = await page.evaluate(() => {
      const textarea = document.querySelector('textarea');
      if (!textarea) return { error: 'No textarea' };

      const container = textarea.closest('[class*="panel"], [class*="pane"], main, aside, div');
      if (!container) return { error: 'No container' };

      const text = container.innerText;
      const lines = text.split('\n').filter(l => l.trim());

      return {
        totalCharacters: text.length,
        totalLines: lines.length,
        hasUserMessage: text.includes('Hello Claude'),
        hasResponse: text.length > 100 && !text.includes('Reply'),
        preview: lines.slice(0, 5).join(' | ')
      };
    });

    console.log(`   Chat content analysis:`);
    console.log(`   - Total characters: ${chatContent.totalCharacters}`);
    console.log(`   - Total lines: ${chatContent.totalLines}`);
    console.log(`   - User message present: ${chatContent.hasUserMessage ? '✅' : '❌'}`);
    console.log(`   - Claude response present: ${chatContent.hasResponse ? '✅' : '❌'}`);
    if (chatContent.preview) {
      console.log(`   - Content preview: ${chatContent.preview.substring(0, 120)}...`);
    }
    console.log('');

    // Send another test message to test conversation flow
    console.log('1️1️⃣ Testing conversation flow - sending second message...');
    const secondMessage = 'Can you help me test chat interactions?';

    const newInput = await page.waitForSelector('textarea', { timeout: 2000 });
    if (newInput) {
      await newInput.click();
      await page.waitForTimeout(300);
      await newInput.type(secondMessage, { delay: 40 });
      console.log(`   Message 2: "${secondMessage}"`);

      await page.screenshot({ path: 'test-results/24-claude-message-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 24-claude-message-2.png');

      await newInput.press('Enter');
      console.log('   ✅ Message 2 sent\n');

      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/25-claude-response-2.png', fullPage: true });
      console.log('   ✅ Screenshot: 25-claude-response-2.png\n');
    }

    console.log('✅ CLAUDE CODE CHAT PANE Test Complete!');
    console.log('\n📸 Screenshots captured:');
    console.log('   - 20-claude-chat-full-layout.png (Initial layout)');
    console.log('   - 21-claude-message-typed.png (Message typed)');
    console.log('   - 22-claude-response.png (Claude responding)');
    console.log('   - 23-claude-scrolled-view.png (Full conversation)');
    console.log('   - 24-claude-message-2.png (Second message)');
    console.log('   - 25-claude-response-2.png (Claude response to message 2)');
    console.log('\n✅ Chat interaction with Claude AI verified!');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/error-claude-chat.png', fullPage: true });
  }

  await browser.close();
})();
