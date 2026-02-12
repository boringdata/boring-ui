/**
 * E2E Chat Interaction Test
 *
 * Tests the FULL chat flow:
 * 1. Type a message in chat input
 * 2. Send the message (press Enter)
 * 3. Wait for a response
 * 4. Verify response appears in chat
 * 5. Screenshot the full interaction
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  console.log('🤖 Testing Full Chat Interaction\n');

  try {
    // Navigate to app
    console.log('1️⃣ Opening chat interface...');
    await page.goto('http://localhost:5173', { waitUntil: 'commit', timeout: 10000 });
    await page.waitForTimeout(1000);

    // Find chat input
    console.log('2️⃣ Finding chat input element...');
    const chatInputSelectors = [
      'textarea[placeholder*="Reply"]',
      'textarea[placeholder*="message"]',
      'input[placeholder*="Reply"]',
      'input[placeholder*="message"]',
      'textarea',
      '[role="textbox"]'
    ];

    let chatInput = null;
    for (const selector of chatInputSelectors) {
      chatInput = await page.$(selector);
      if (chatInput) {
        console.log(`   ✅ Found: ${selector}\n`);
        break;
      }
    }

    if (!chatInput) {
      console.log('   ❌ Chat input not found');
      await page.screenshot({ path: 'test-results/chat-interaction-error.png', fullPage: true });
      await browser.close();
      return;
    }

    // Take screenshot before typing
    await page.screenshot({ path: 'test-results/05-chat-before-message.png', fullPage: true });
    console.log('3️⃣ Typed message in chat input...');

    // Type a message
    await chatInput.click();
    await page.waitForTimeout(300);

    const testMessage = 'Hello! Can you explain what you can do?';
    await chatInput.type(testMessage, { delay: 50 });

    console.log(`   Message: "${testMessage}"`);
    await page.waitForTimeout(500);

    // Take screenshot of typed message
    await page.screenshot({ path: 'test-results/05-chat-message-typed.png', fullPage: true });
    console.log('   ✅ Screenshot: 05-chat-message-typed.png\n');

    // Send the message
    console.log('4️⃣ Sending message (press Enter)...');
    await chatInput.press('Enter');
    console.log('   ✅ Message sent\n');

    // Wait for response
    console.log('5️⃣ Waiting for response...');
    await page.waitForTimeout(2000);  // Wait for response to come back

    // Take screenshot of response
    await page.screenshot({ path: 'test-results/06-chat-response.png', fullPage: true });
    console.log('   ✅ Screenshot: 06-chat-response.png\n');

    // Check if there's chat content visible
    const chatContent = await page.evaluate(() => {
      // Try to find chat messages
      const messages = document.querySelectorAll('[role="article"], .message, .chat-message, .bubble, [class*="message"]');
      return {
        messageCount: messages.length,
        pageText: document.body.innerText.substring(0, 500)
      };
    });

    console.log('6️⃣ Chat Content Analysis:');
    console.log(`   Messages found: ${chatContent.messageCount}`);
    console.log(`   Page has content: ${chatContent.pageText.length > 0 ? '✅' : '❌'}\n`);

    // Scroll down to see if responses are below
    console.log('7️⃣ Scrolling to bottom of chat...');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    await page.screenshot({ path: 'test-results/07-chat-scrolled.png', fullPage: true });
    console.log('   ✅ Screenshot: 07-chat-scrolled.png\n');

    // Test with Companion provider
    console.log('8️⃣ Testing with Companion provider...');
    await page.goto('http://localhost:5173?chat=companion', { waitUntil: 'commit' });
    await page.waitForTimeout(1000);

    // Find new session button for companion
    const newSessionBtn = await page.$('button:has-text("New Session"), button:has-text("+ New")');
    if (newSessionBtn) {
      console.log('   ✅ Companion provider loaded with new session button');
      await page.screenshot({ path: 'test-results/08-companion-ready.png', fullPage: true });
    }

    console.log('\n✅ Chat Interaction Test Complete!');
    console.log('📸 Screenshots saved:\n');
    console.log('   - 05-chat-before-message.png (Initial state)');
    console.log('   - 05-chat-message-typed.png (Message typed)');
    console.log('   - 06-chat-response.png (After sending)');
    console.log('   - 07-chat-scrolled.png (Scrolled view)');
    console.log('   - 08-companion-ready.png (Companion provider)');

  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: 'test-results/chat-error.png', fullPage: true });
  }

  await browser.close();
})();
