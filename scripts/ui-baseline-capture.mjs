#!/usr/bin/env node

import fs from 'node:fs/promises'
import path from 'node:path'
import { spawn } from 'node:child_process'

const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
const DEFAULT_URL = process.env.UI_BASE_URL || 'http://127.0.0.1:5173/'
const DEFAULT_OUT_DIR = process.env.OUT_DIR || path.join(process.cwd(), 'artifacts', 'ui-baselines', timestamp)
const DEFAULT_MATRIX = process.env.UI_BASELINE_VIEWPORTS
  || 'desktop=1600x1000,laptop=1366x900,tablet=1024x768'

const args = process.argv.slice(2)

const readArg = (name, fallback = '') => {
  const idx = args.indexOf(name)
  if (idx === -1 || idx + 1 >= args.length) return fallback
  return args[idx + 1]
}

const hasFlag = (name) => args.includes(name)

const baseUrl = readArg('--url', DEFAULT_URL)
const outDir = readArg('--out', DEFAULT_OUT_DIR)
const matrixArg = readArg('--matrix', DEFAULT_MATRIX)
const reducedMotionArg = readArg('--reduced-motion', 'reduce').toLowerCase()
const reducedMotion = reducedMotionArg === 'no-preference' ? 'no-preference' : 'reduce'
const headed = hasFlag('--headed')

const parseMatrix = (value) => {
  return String(value)
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [namePart, viewportPart] = entry.includes('=')
        ? entry.split('=')
        : [entry, entry]
      const name = String(namePart || '').trim()
      const viewport = String(viewportPart || '').trim()
      if (!name || !viewport) {
        throw new Error(`Invalid matrix entry "${entry}"`)
      }
      if (!/^\d+x\d+$/i.test(viewport)) {
        throw new Error(`Invalid viewport "${viewport}" in matrix entry "${entry}"`)
      }
      return { name, viewport }
    })
}

const viewportMatrix = parseMatrix(matrixArg)

const runOne = async ({ name, viewport }, logPath) => {
  const runOutDir = path.join(outDir, name)
  await fs.mkdir(runOutDir, { recursive: true })

  const commandArgs = [
    path.join('scripts', 'ui-layout-matrix-check.mjs'),
    '--url', baseUrl,
    '--out', runOutDir,
    '--viewport', viewport,
    '--reduced-motion', reducedMotion,
  ]
  if (headed) commandArgs.push('--headed')

  const startedAt = new Date().toISOString()
  const child = spawn(process.execPath, commandArgs, {
    cwd: process.cwd(),
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  const chunks = []
  const writeLine = async (line) => {
    await fs.appendFile(logPath, `${line}\n`, 'utf8')
    process.stdout.write(`${line}\n`)
  }

  child.stdout.on('data', (chunk) => {
    const text = String(chunk)
    chunks.push(text)
    process.stdout.write(text)
  })
  child.stderr.on('data', (chunk) => {
    const text = String(chunk)
    chunks.push(text)
    process.stderr.write(text)
  })

  const exitCode = await new Promise((resolve) => {
    child.on('close', (code) => resolve(code ?? 1))
  })

  const finishedAt = new Date().toISOString()
  await writeLine(`[ui-baseline] ${name} viewport=${viewport} reduced_motion=${reducedMotion} exit=${exitCode}`)

  return {
    name,
    viewport,
    reduced_motion: reducedMotion,
    out_dir: runOutDir,
    started_at: startedAt,
    finished_at: finishedAt,
    exit_code: exitCode,
    passed: exitCode === 0,
    log_excerpt: chunks.join('').slice(-4000),
  }
}

const run = async () => {
  await fs.mkdir(outDir, { recursive: true })
  const logPath = path.join(outDir, 'run.log')

  await fs.writeFile(
    logPath,
    [
      `[ui-baseline] started_at=${new Date().toISOString()}`,
      `[ui-baseline] base_url=${baseUrl}`,
      `[ui-baseline] out_dir=${outDir}`,
      `[ui-baseline] matrix=${viewportMatrix.map((entry) => `${entry.name}=${entry.viewport}`).join(',')}`,
      `[ui-baseline] reduced_motion=${reducedMotion}`,
      `[ui-baseline] headed=${headed}`,
    ].join('\n') + '\n',
    'utf8',
  )

  const results = []
  for (const entry of viewportMatrix) {
    // eslint-disable-next-line no-await-in-loop
    const result = await runOne(entry, logPath)
    results.push(result)
  }

  const summary = {
    base_url: baseUrl,
    out_dir: outDir,
    reduced_motion: reducedMotion,
    headed,
    matrix: viewportMatrix,
    runs: results,
    passed: results.every((runResult) => runResult.passed),
    generated_at: new Date().toISOString(),
  }

  const summaryPath = path.join(outDir, 'summary.json')
  await fs.writeFile(summaryPath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8')

  if (!summary.passed) {
    process.stderr.write(`[ui-baseline] failed - see ${summaryPath}\n`)
    process.exit(1)
  }

  process.stdout.write(`[ui-baseline] passed - artifacts at ${outDir}\n`)
}

run().catch((error) => {
  console.error(error)
  process.exit(1)
})
