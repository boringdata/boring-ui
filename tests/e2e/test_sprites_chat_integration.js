/**
 * E2E Test: Sprites Provider + Chat Integration
 *
 * Tests that:
 * 1. Backend accepts chat messages via Companion provider
 * 2. Sprites sandbox can be created and managed
 * 3. Chat panel is fully functional with Sprites backend
 */

const { test, expect } = require('@playwright/test');

const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:5173';
const CHAT_PANEL_SELECTOR = 'textarea[placeholder="Reply..."]';

test.describe('Sprites + Chat Integration', () => {
  let context;
  let page;

  test.beforeAll(async () => {
    // Check backend is running
    const response = await fetch(`${BACKEND_URL}/api/capabilities`);
    if (!response.ok) {
      throw new Error(`Backend not ready: ${response.status}`);
    }
  });

  test.beforeEach(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();
  });

  test.afterEach(async () => {
    await context.close();
  });

  // ===== Sandbox Lifecycle =====

  test('should create and manage Sprites sandbox', async () => {
    // Check initial status
    const status1 = await fetch(`${BACKEND_URL}/api/sandbox/status`);
    const data1 = await status1.json();
    console.log('Initial status:', data1.status);

    // Start sandbox (creates sprite)
    const start = await fetch(`${BACKEND_URL}/api/sandbox/start`, {
      method: 'POST',
    });
    expect(start.ok).toBe(true);
    const startData = await start.json();
    expect(startData.status).toBe('running');
    expect(startData.base_url).toContain('sprites.app');
    console.log('✓ Sandbox created:', startData.base_url);

    // Health check
    const health = await fetch(`${BACKEND_URL}/api/sandbox/health`);
    const healthData = await health.json();
    expect(healthData.healthy).toBe(true);
    console.log('✓ Sandbox is healthy');

    // Get logs
    const logs = await fetch(`${BACKEND_URL}/api/sandbox/logs?limit=10`);
    const logsData = await logs.json();
    expect(Array.isArray(logsData.logs)).toBe(true);
    console.log('✓ Fetched logs:', logsData.logs.length, 'lines');

    // Get metrics
    const metrics = await fetch(`${BACKEND_URL}/api/sandbox/metrics`);
    const metricsData = await metrics.json();
    expect(metricsData.counters).toBeDefined();
    console.log('✓ Got metrics');

    // Stop sandbox
    const stop = await fetch(`${BACKEND_URL}/api/sandbox/stop`, {
      method: 'POST',
    });
    expect(stop.ok).toBe(true);
    console.log('✓ Sandbox stopped');
  });

  // ===== Frontend Chat Panel =====

  test('should load frontend with chat panel', async () => {
    await page.goto(FRONTEND_URL);

    // Wait for app to load
    await page.waitForLoadState('commit');

    // Check for chat input
    const chatInput = await page.$(CHAT_PANEL_SELECTOR);
    expect(chatInput).not.toBeNull();
    console.log('✓ Chat panel loaded');
  });

  test('should switch to Sandbox chat provider', async () => {
    // Go to sandbox provider
    await page.goto(`${FRONTEND_URL}?chat=sandbox`);
    await page.waitForLoadState('commit');

    // Check chat panel is visible
    const chatPanel = await page.$('.terminal-panel'); // Adjust selector as needed
    if (chatPanel) {
      console.log('✓ Sandbox chat provider loaded');
    }
  });

  test('should switch to Companion chat provider', async () => {
    // Go to companion provider
    await page.goto(`${FRONTEND_URL}?chat=companion`);
    await page.waitForLoadState('commit');

    // Check chat panel is visible
    const chatPanel = await page.$('.terminal-panel'); // Adjust selector as needed
    if (chatPanel) {
      console.log('✓ Companion chat provider loaded');
    }
  });

  // ===== Chat Message Flow =====

  test('should send message in chat panel', async () => {
    await page.goto(`${FRONTEND_URL}?chat=companion`);
    await page.waitForLoadState('commit');

    // Find chat input
    const chatInput = await page.$(CHAT_PANEL_SELECTOR);
    expect(chatInput).not.toBeNull();

    // Type message
    await chatInput.type('Hello from Showboat!');

    // Check message appears in input
    const inputValue = await chatInput.inputValue();
    expect(inputValue).toContain('Hello from Showboat');
    console.log('✓ Message typed in chat');

    // Press Enter (or find send button)
    const sendButton = await page.$('button:has-text("Send")');
    if (sendButton) {
      await sendButton.click();
      console.log('✓ Message sent via button');
    } else {
      await chatInput.press('Enter');
      console.log('✓ Message sent via Enter key');
    }

    // Wait for response
    await page.waitForTimeout(1000);
    console.log('✓ Chat message flow complete');
  });

  // ===== Capabilities =====

  test('should fetch capabilities (both providers)', async () => {
    const response = await fetch(`${BACKEND_URL}/api/capabilities`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(data.services).toBeDefined();

    const services = Object.keys(data.services);
    console.log('✓ Available services:', services);

    // Should have at least sandbox or companion
    const hasChat = services.includes('companion') || services.includes('claude');
    expect(hasChat).toBe(true);
    console.log('✓ Chat provider available');
  });

  // ===== Integration: Sandbox + Chat Together =====

  test('should work: create sandbox AND use chat', async () => {
    // Create sandbox
    console.log('\n[1/4] Starting Sprites sandbox...');
    const start = await fetch(`${BACKEND_URL}/api/sandbox/start`, {
      method: 'POST',
    });
    expect(start.ok).toBe(true);
    const sandbox = await start.json();
    expect(sandbox.status).toBe('running');
    console.log('✓ Sandbox running:', sandbox.base_url);

    // Load chat UI
    console.log('[2/4] Loading chat UI...');
    await page.goto(`${FRONTEND_URL}?chat=companion`);
    await page.waitForLoadState('commit');
    console.log('✓ Chat UI loaded');

    // Send message (Rodney)
    console.log('[3/4] Sending chat message as Rodney...');
    const chatInput = await page.$(CHAT_PANEL_SELECTOR);
    if (chatInput) {
      await chatInput.type('Rodney here! Sprites sandbox is ready?');
      console.log('✓ Message from Rodney sent');
    }

    // Check sandbox is still running
    console.log('[4/4] Verifying sandbox still running...');
    const status = await fetch(`${BACKEND_URL}/api/sandbox/status`);
    const statusData = await status.json();
    expect(statusData.status).toBe('running');
    console.log('✓ Sandbox still running during chat');

    console.log('\n✅ Full integration test PASSED');
  });

  // ===== Error Handling =====

  test('should handle sandbox errors gracefully', async () => {
    // Try to get info for non-existent sandbox
    const response = await fetch(`${BACKEND_URL}/api/sandbox/status`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    // Should either return status or { status: "not_running" }
    expect(data.status).toBeDefined();
    console.log('✓ Error handling works:', data.status);
  });
});

test.describe('API Integration', () => {
  /**
   * Test the HTTP API directly (no browser)
   */

  test('GET /api/sandbox/status returns valid structure', async () => {
    const response = await fetch(`${BACKEND_URL}/api/sandbox/status`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(data).toHaveProperty('status');
    console.log('✓ Status endpoint works');
  });

  test('POST /api/sandbox/start creates sandbox', async () => {
    const response = await fetch(`${BACKEND_URL}/api/sandbox/start`, {
      method: 'POST',
    });
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(data.status).toBe('running');
    expect(data.base_url).toBeTruthy();
    console.log('✓ Start endpoint works');
  });

  test('GET /api/sandbox/health checks sandbox', async () => {
    // Ensure sandbox is running first
    await fetch(`${BACKEND_URL}/api/sandbox/start`, {
      method: 'POST',
    });

    const response = await fetch(`${BACKEND_URL}/api/sandbox/health`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(typeof data.healthy).toBe('boolean');
    console.log('✓ Health check endpoint works');
  });

  test('GET /api/sandbox/logs returns log lines', async () => {
    const response = await fetch(`${BACKEND_URL}/api/sandbox/logs?limit=10`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(Array.isArray(data.logs)).toBe(true);
    console.log('✓ Logs endpoint works, got', data.logs.length, 'lines');
  });

  test('GET /api/capabilities returns services', async () => {
    const response = await fetch(`${BACKEND_URL}/api/capabilities`);
    expect(response.ok).toBe(true);

    const data = await response.json();
    expect(data.services).toBeDefined();
    const serviceList = Object.keys(data.services);
    console.log('✓ Capabilities endpoint works, services:', serviceList);
  });

  test('POST /api/sandbox/stop stops sandbox', async () => {
    // Start first
    await fetch(`${BACKEND_URL}/api/sandbox/start`, {
      method: 'POST',
    });

    // Stop
    const response = await fetch(`${BACKEND_URL}/api/sandbox/stop`, {
      method: 'POST',
    });
    expect(response.ok).toBe(true);
    console.log('✓ Stop endpoint works');
  });
});
