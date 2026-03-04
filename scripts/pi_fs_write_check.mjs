import { chromium } from '@playwright/test'

const apiKey = process.env.ANTHROPIC_API_KEY || ''
if (!apiKey) {
  console.error('ANTHROPIC_API_KEY missing')
  process.exit(1)
}

const ts = Date.now()
const fname = `pi-created-${ts}.md`
const marker = `pi-fs-${ts}`

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()
await page.goto('http://127.0.0.1:5180/', { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.file-tree-title, .file-tree-scroll')
await page.evaluate((k) => { window.__PI_TEST_API_KEY__ = k }, apiKey)

const input = page.locator('pi-chat-panel textarea, pi-chat-panel input[type="text"]').first()
await input.click()
await input.fill(`Create file ${fname} with exactly this content: ${marker}. Use filesystem tools only, then open_file ${fname}, then answer DONE.`)
await input.press('Enter')
await page.waitForTimeout(30000)

const info = await page.evaluate(({ targetName }) => {
  const queryDeep = (root, selector) => {
    const out = []
    const walk = (node) => {
      if (!node) return
      if (typeof node.querySelectorAll === 'function') {
        try { out.push(...node.querySelectorAll(selector)) } catch {}
      }
      const children = node.children ? Array.from(node.children) : []
      for (const child of children) {
        if (child.shadowRoot) walk(child.shadowRoot)
        walk(child)
      }
    }
    walk(root)
    return out
  }

  const panel = queryDeep(document, 'pi-chat-panel')[0]
  const messages = Array.isArray(panel?.agent?.state?.messages) ? panel.agent.state.messages : []
  const writeResult = messages.find((m) => m?.role === 'toolResult' && m?.toolName === 'write_file' &&
    Array.isArray(m?.content) && m.content.some((c) => String(c?.text || '').includes(targetName)))
  const openResult = messages.find((m) => m?.role === 'toolResult' && m?.toolName === 'open_file' &&
    Array.isArray(m?.content) && m.content.some((c) => String(c?.text || '').includes(targetName)))
  const done = messages.some((m) => m?.role === 'assistant' && Array.isArray(m?.content) && m.content.some((c) => String(c?.text || '').includes('DONE')))

  return {
    toolNames: Array.from(new Set(messages.filter((m) => m?.role === 'toolResult').map((m) => m.toolName))).filter(Boolean),
    hasWriteResult: !!writeResult,
    hasOpenResult: !!openResult,
    done,
  }
}, { targetName: fname })

const treeHasFile = await page.locator('.file-item', { hasText: fname }).count()

console.log(JSON.stringify({ fname, marker, info, treeHasFile }, null, 2))
await browser.close()
