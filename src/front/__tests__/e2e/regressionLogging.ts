import fs from 'node:fs/promises'
import type { Page, TestInfo } from '@playwright/test'

type RegressionEvent = {
  ts: string
  kind: string
  detail: Record<string, unknown>
}

type RegressionStep = {
  name: string
  status: 'passed' | 'failed'
  startedAt: string
  finishedAt: string
  error?: string
}

const timestamp = () => new Date().toISOString()

export const createRegressionLogger = (
  page: Page,
  testInfo: TestInfo,
  context: Record<string, unknown>,
) => {
  const events: RegressionEvent[] = []
  const steps: RegressionStep[] = []

  const record = (kind: string, detail: Record<string, unknown>) => {
    events.push({
      ts: timestamp(),
      kind,
      detail,
    })
  }

  page.on('console', (message) => {
    record('console', {
      level: message.type(),
      text: message.text(),
    })
  })

  page.on('pageerror', (error) => {
    record('pageerror', {
      message: error.message,
      stack: error.stack ?? '',
    })
  })

  page.on('requestfailed', (request) => {
    record('requestfailed', {
      method: request.method(),
      url: request.url(),
      failure: request.failure()?.errorText ?? '',
    })
  })

  page.on('response', (response) => {
    if (response.status() < 400) {
      return
    }
    record('http_error', {
      method: response.request().method(),
      status: response.status(),
      url: response.url(),
    })
  })

  return {
    async note(name: string, detail: Record<string, unknown>) {
      record(`note:${name}`, detail)
    },

    async step<T>(name: string, callback: () => Promise<T>) {
      const startedAt = timestamp()
      try {
        const result = await callback()
        steps.push({
          name,
          status: 'passed',
          startedAt,
          finishedAt: timestamp(),
        })
        return result
      } catch (error) {
        steps.push({
          name,
          status: 'failed',
          startedAt,
          finishedAt: timestamp(),
          error: error instanceof Error ? error.message : String(error),
        })
        throw error
      }
    },

    async flush() {
      const browserEventsPath = testInfo.outputPath('browser-events.ndjson')
      const stepLogPath = testInfo.outputPath('step-log.json')

      const ndjson = events.map((entry) => JSON.stringify(entry)).join('\n')
      await fs.writeFile(browserEventsPath, ndjson ? `${ndjson}\n` : '', 'utf8')
      await fs.writeFile(
        stepLogPath,
        JSON.stringify(
          {
            context,
            finalUrl: page.url(),
            steps,
          },
          null,
          2,
        ),
        'utf8',
      )

      await testInfo.attach('browser-events', {
        path: browserEventsPath,
        contentType: 'application/x-ndjson',
      })
      await testInfo.attach('step-log', {
        path: stepLogPath,
        contentType: 'application/json',
      })
    },
  }
}
