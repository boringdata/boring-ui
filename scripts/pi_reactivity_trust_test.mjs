#!/usr/bin/env node
import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { chromium } from 'playwright'

const defaults = {
  frontend: 'http://213.32.19.186:5190/?agent_mode=pi',
  backend: 'http://0.0.0.0:3456',
  prompt: 'Ping from trust test. Reply with one short sentence.',
  out: '.evidence/pi-reactivity-result.json',
  screenshot: '.evidence/pi-reactivity-ui.png',
  ttftMaxMs: 2000,
  totalMaxMs: 12000,
  hangMaxMs: 25000,
  maxTotalMs: 30000,
  settleQuietMs: 1200,
  waitPanelMs: 20000,
  providerKey: '',
}

function parseArgs(argv) {
  const opts = { ...defaults }
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i]
    const next = argv[i + 1]
    if (!key.startsWith('--') || next == null) continue
    const value = next
    if (key === '--frontend') opts.frontend = value
    if (key === '--backend') opts.backend = value
    if (key === '--prompt') opts.prompt = value
    if (key === '--out') opts.out = value
    if (key === '--screenshot') opts.screenshot = value
    if (key === '--ttft-max-ms') opts.ttftMaxMs = Number(value)
    if (key === '--total-max-ms') opts.totalMaxMs = Number(value)
    if (key === '--hang-max-ms') opts.hangMaxMs = Number(value)
    if (key === '--max-total-ms') opts.maxTotalMs = Number(value)
    if (key === '--settle-quiet-ms') opts.settleQuietMs = Number(value)
    if (key === '--wait-panel-ms') opts.waitPanelMs = Number(value)
    if (key === '--provider-key') opts.providerKey = value
  }
  return opts
}

function nowIso() {
  return new Date().toISOString()
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function requestCategory(url) {
  if (/\/api\/|\/health\b/i.test(url)) return 'backend_api'
  if (/api\.anthropic\.com/i.test(url)) return 'anthropic'
  if (/api\.openai\.com/i.test(url) || /chatgpt\.com\/backend-api/i.test(url)) return 'openai'
  if (/googleapis\.com/i.test(url) || /generativelanguage/i.test(url) || /cloudcode-pa\.googleapis\.com/i.test(url)) return 'google'
  return null
}

async function fetchJson(url) {
  const res = await fetch(url)
  const body = await res.text()
  let json = null
  try {
    json = JSON.parse(body)
  } catch {
    json = null
  }
  return { status: res.status, ok: res.ok, json, body }
}

async function run() {
  const opts = parseArgs(process.argv)
  const startedAt = nowIso()

  const thresholds = {
    ttft_max_ms: opts.ttftMaxMs,
    total_max_ms: opts.totalMaxMs,
    stream_hang_max_ms: opts.hangMaxMs,
  }

  const backend = {
    base_url: opts.backend,
    health: null,
    capabilities: null,
    errors: [],
  }

  try {
    backend.health = await fetchJson(`${opts.backend}/health`)
  } catch (error) {
    backend.errors.push(`health request failed: ${error?.message || String(error)}`)
  }
  try {
    backend.capabilities = await fetchJson(`${opts.backend}/api/capabilities`)
  } catch (error) {
    backend.errors.push(`capabilities request failed: ${error?.message || String(error)}`)
  }

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1536, height: 960 },
  })
  if (opts.providerKey) {
    await context.addInitScript((value) => {
      window.__PI_TEST_API_KEY__ = value
    }, opts.providerKey)
  }
  const page = await context.newPage()

  const requestState = {
    all: [],
    provider: [],
  }
  const openRequests = new Map()

  page.on('request', (request) => {
    const started = Date.now()
    const item = {
      id: `${started}-${Math.random().toString(36).slice(2, 8)}`,
      ts: started,
      method: request.method(),
      url: request.url(),
      category: requestCategory(request.url()),
      resourceType: request.resourceType(),
    }
    requestState.all.push(item)
    openRequests.set(request, item)
    if (item.category) requestState.provider.push(item)
  })

  page.on('response', (response) => {
    const request = response.request()
    const item = openRequests.get(request)
    if (!item) return
    item.status = response.status()
    item.doneTs = Date.now()
    item.durationMs = item.doneTs - item.ts
    openRequests.delete(request)
  })

  page.on('requestfailed', (request) => {
    const item = openRequests.get(request)
    if (!item) return
    item.failed = request.failure()?.errorText || 'requestfailed'
    item.doneTs = Date.now()
    item.durationMs = item.doneTs - item.ts
    openRequests.delete(request)
  })

  const navigation = {
    url: opts.frontend,
    ok: true,
    error: null,
  }

  try {
    await page.goto(opts.frontend, { waitUntil: 'domcontentloaded', timeout: 30000 })
  } catch (error) {
    navigation.ok = false
    navigation.error = error?.message || String(error)
  }

  let uiProbe = {
    ok: false,
    error: 'navigation_failed',
    submitAttempted: false,
  }

  if (navigation.ok) {
    try {
      await page.waitForTimeout(300)
      const expandButton = page.getByRole('button', { name: 'Expand agent panel' })
      if (await expandButton.count()) {
        await expandButton.first().click({ timeout: 3000 })
      }

      await page.waitForFunction(() => {
        const host = document.querySelector('[data-testid="pi-native-adapter"] > div')
        const root = host?.shadowRoot
        const panel = root?.querySelector('pi-chat-panel')
        const textarea = panel?.querySelector('message-editor textarea')
        return Boolean(host && root && panel && textarea)
      }, {}, { timeout: opts.waitPanelMs })

      uiProbe = await page.evaluate(async ({ prompt, maxTotalMs, settleQuietMs }) => {
        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

        const host = document.querySelector('[data-testid="pi-native-adapter"] > div')
        const root = host?.shadowRoot
        const panel = root?.querySelector('pi-chat-panel')
        const editor = panel?.querySelector('message-editor')
        const textarea = panel?.querySelector('message-editor textarea')

        if (!host || !root || !panel || !editor || !textarea) {
          return { ok: false, error: 'pi_panel_or_textarea_not_found', submitAttempted: false }
        }

        const snapshot = () => {
          const clone = panel.cloneNode(true)
          clone.querySelectorAll('message-editor').forEach((node) => node.remove())
          return (clone.textContent || '').replace(/\s+/g, ' ').trim()
        }

        const baseline = snapshot()
        const start = performance.now()
        let firstVisibleUpdateMs = null
        let mutationCount = 0
        let lastMutationAt = start

        const observer = new MutationObserver(() => {
          mutationCount += 1
          lastMutationAt = performance.now()
          if (firstVisibleUpdateMs == null) {
            const current = snapshot()
            if (current !== baseline) {
              firstVisibleUpdateMs = Math.round(performance.now() - start)
            }
          }
        })
        observer.observe(panel, { childList: true, subtree: true, characterData: true })

        textarea.focus()
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
        if (nativeSetter) {
          nativeSetter.call(textarea, prompt)
        } else {
          textarea.value = prompt
        }
        textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }))
        textarea.dispatchEvent(new Event('change', { bubbles: true, composed: true }))
        await sleep(120)

        const buttons = Array.from(editor.querySelectorAll('button'))
        const sendButton = buttons.length > 0 ? buttons[buttons.length - 1] : null
        const sendEnabledBeforeClick = Boolean(sendButton && !sendButton.disabled)
        let sendClicked = false
        let usedDirectOnSend = false
        if (sendEnabledBeforeClick) {
          sendButton.click()
          sendClicked = true
        } else {
          textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true }))
          textarea.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true }))
        }
        await sleep(120)
        if (mutationCount === 0 && textarea.value.trim() && typeof editor.onSend === 'function') {
          editor.onSend(textarea.value, Array.isArray(editor.attachments) ? editor.attachments : [])
          usedDirectOnSend = true
        }

        let doneReason = null
        let hasApiKeyPrompt = false
        let finalTextSample = ''

        while ((performance.now() - start) < maxTotalMs) {
          await sleep(120)
          const currentText = snapshot()
          finalTextSample = currentText.slice(0, 500)
          const elapsed = performance.now() - start
          const quietForMs = performance.now() - lastMutationAt
          const textareaCleared = textarea.value.length === 0

          hasApiKeyPrompt = /api key|authentication required|set api key/i.test(currentText)
          const hasError = /error|failed|forbidden|unauthorized|rate limit/i.test(currentText)

          if (hasApiKeyPrompt) {
            doneReason = 'api_key_prompt'
            break
          }
          if (hasError && firstVisibleUpdateMs != null) {
            doneReason = 'error_visible'
            break
          }
          if (firstVisibleUpdateMs != null && quietForMs >= settleQuietMs && textareaCleared) {
            doneReason = 'settled_after_submit'
            break
          }
          if (firstVisibleUpdateMs == null && elapsed >= maxTotalMs) {
            doneReason = 'timeout_no_visible_update'
            break
          }
        }

        observer.disconnect()

        const totalResponseMs = Math.round(performance.now() - start)
        if (!doneReason) {
          doneReason = firstVisibleUpdateMs == null ? 'timeout_no_visible_update' : 'timeout_not_settled'
        }

        return {
          ok: true,
          submitAttempted: true,
          sendEnabledBeforeClick,
          sendClicked,
          usedDirectOnSend,
          firstVisibleUpdateMs,
          totalResponseMs,
          doneReason,
          mutationCount,
          hasApiKeyPrompt,
          finalTextSample,
        }
      }, {
        prompt: opts.prompt,
        maxTotalMs: opts.maxTotalMs,
        settleQuietMs: opts.settleQuietMs,
      })
    } catch (error) {
      uiProbe = {
        ok: false,
        error: error?.message || String(error),
        submitAttempted: false,
      }
    }
  }

  await page.screenshot({ path: opts.screenshot, fullPage: true })

  const finishedAtMs = Date.now()
  const providerRequests = requestState.provider.map((item) => ({
    ...item,
    inFlight: !item.doneTs,
    ageMs: (item.doneTs || finishedAtMs) - item.ts,
  }))

  const streamHangDetected = providerRequests.some((item) => item.inFlight && item.ageMs > opts.hangMaxMs)

  const failures = []
  if (!navigation.ok) failures.push(`navigation_failed: ${navigation.error}`)
  if (!uiProbe.ok) failures.push(`ui_probe_failed: ${uiProbe.error || 'unknown'}`)

  if (uiProbe.ok) {
    if (uiProbe.sendEnabledBeforeClick === false && uiProbe.sendClicked === false) {
      failures.push('send_action_not_enabled')
    }
    if (!isFiniteNumber(uiProbe.firstVisibleUpdateMs)) {
      failures.push('ttft_missing')
    } else if (uiProbe.firstVisibleUpdateMs > opts.ttftMaxMs) {
      failures.push(`ttft_exceeded:${uiProbe.firstVisibleUpdateMs}>${opts.ttftMaxMs}`)
    }

    if (!isFiniteNumber(uiProbe.totalResponseMs)) {
      failures.push('total_response_missing')
    } else if (uiProbe.totalResponseMs > opts.totalMaxMs) {
      failures.push(`total_response_exceeded:${uiProbe.totalResponseMs}>${opts.totalMaxMs}`)
    }

    if (String(uiProbe.doneReason || '').startsWith('timeout')) {
      failures.push(`stream_timeout:${uiProbe.doneReason}`)
    }
  }

  if (streamHangDetected) {
    failures.push('provider_request_hang_detected')
  }

  const capabilitiesFeatures = backend.capabilities?.json?.features || {}
  if (backend.capabilities?.ok && capabilitiesFeatures.pi !== true) {
    failures.push('backend_pi_feature_disabled')
  }

  const apiRequests = requestState.all
    .filter((item) => item.category === 'backend_api')
    .map((item) => ({
      method: item.method,
      status: item.status || null,
      in_flight: !item.doneTs,
      duration_ms: item.durationMs || null,
      url: item.url,
      failed: item.failed || null,
    }))
  if (apiRequests.length === 0) {
    failures.push('frontend_never_requested_backend_api')
  }

  const result = {
    probe: 'pi_reactivity_trust_test',
    started_at: startedAt,
    finished_at: nowIso(),
    frontend_url: opts.frontend,
    thresholds,
    pass: failures.length === 0,
    failures,
    backend,
    navigation,
    ui_probe: uiProbe,
    network_summary: {
      total_requests: requestState.all.length,
      api_requests: apiRequests.length,
      api_request_details: apiRequests.slice(0, 30),
      provider_requests: providerRequests.length,
      provider_requests_completed: providerRequests.filter((r) => !r.inFlight).length,
      provider_requests_in_flight: providerRequests.filter((r) => r.inFlight).length,
      stream_hang_detected: streamHangDetected,
      provider_request_details: providerRequests.map((r) => ({
        method: r.method,
        category: r.category,
        status: r.status || null,
        in_flight: r.inFlight,
        duration_ms: r.durationMs || null,
        age_ms: r.ageMs,
        url: r.url,
      })),
    },
    artifacts: {
      screenshot: opts.screenshot,
      json: opts.out,
    },
  }

  await fs.mkdir(path.dirname(opts.out), { recursive: true })
  await fs.mkdir(path.dirname(opts.screenshot), { recursive: true })
  await fs.writeFile(opts.out, `${JSON.stringify(result, null, 2)}\n`, 'utf8')

  await context.close()
  await browser.close()

  console.log(JSON.stringify(result, null, 2))
}

run().catch((error) => {
  const payload = {
    probe: 'pi_reactivity_trust_test',
    pass: false,
    fatal_error: error?.message || String(error),
  }
  console.error(JSON.stringify(payload, null, 2))
  process.exitCode = 1
})
