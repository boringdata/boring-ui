#!/usr/bin/env node
/* global process, console */

import fs from 'node:fs/promises'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
const outDir = path.join(process.cwd(), 'artifacts', 'root-entrypoint-smoke', timestamp)
const logPath = path.join(outDir, 'build.log')

const requireCjs = createRequire(import.meta.url)

const appendLog = async (line) => {
  await fs.appendFile(logPath, `${line}\n`, 'utf8')
}

const runCommand = async (command, commandArgs, label) => {
  await appendLog(`\n[${label}] ${command} ${commandArgs.join(' ')}`)
  const child = spawn(command, commandArgs, {
    cwd: process.cwd(),
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  let combined = ''
  child.stdout.on('data', (chunk) => {
    const text = String(chunk)
    combined += text
    process.stdout.write(text)
  })
  child.stderr.on('data', (chunk) => {
    const text = String(chunk)
    combined += text
    process.stderr.write(text)
  })

  const exitCode = await new Promise((resolve) => {
    child.on('close', (code) => resolve(code ?? 1))
  })

  await appendLog(combined)
  await appendLog(`[${label}] exit_code=${exitCode}`)
  if (exitCode !== 0) {
    throw new Error(`${label} failed with exit code ${exitCode}`)
  }
}

const fileExists = async (filePath) => {
  try {
    await fs.stat(filePath)
    return true
  } catch {
    return false
  }
}

const run = async () => {
  await fs.mkdir(outDir, { recursive: true })
  await fs.writeFile(
    logPath,
    `[root-entrypoint-smoke] started_at=${new Date().toISOString()}\n`,
    'utf8',
  )

  await runCommand('npm', ['run', 'build:lib', '--', '--debug'], 'build:lib')

  const packageJson = JSON.parse(await fs.readFile(path.join(process.cwd(), 'package.json'), 'utf8'))
  const distEsmPath = path.join(process.cwd(), 'dist', 'boring-ui.js')
  const distCjsPath = path.join(process.cwd(), 'dist', 'boring-ui.cjs')
  const distCssPath = path.join(process.cwd(), 'dist', 'style.css')

  const distChecks = {
    esm_exists: await fileExists(distEsmPath),
    cjs_exists: await fileExists(distCjsPath),
    css_exists: await fileExists(distCssPath),
  }
  if (!distChecks.esm_exists || !distChecks.cjs_exists || !distChecks.css_exists) {
    throw new Error(`Expected dist entrypoints missing: ${JSON.stringify(distChecks)}`)
  }

  const exportMap = packageJson.exports || {}
  const rootExport = exportMap['.'] || {}
  const cssExport = exportMap['./style.css']
  if (rootExport.import !== './dist/boring-ui.js' || rootExport.require !== './dist/boring-ui.cjs') {
    throw new Error(`Unexpected root export map: ${JSON.stringify(rootExport)}`)
  }
  if (cssExport !== './dist/style.css') {
    throw new Error(`Unexpected CSS export map: ${JSON.stringify(cssExport)}`)
  }

  const resolvedImportUrl = await import.meta.resolve('boring-ui')
  const resolvedImportCssUrl = await import.meta.resolve('boring-ui/style.css')
  const resolvedRequirePath = requireCjs.resolve('boring-ui')
  const resolvedRequireCssPath = requireCjs.resolve('boring-ui/style.css')
  const resolvedImportPath = fileURLToPath(resolvedImportUrl)
  const resolvedImportCssPath = fileURLToPath(resolvedImportCssUrl)

  if (resolvedImportPath !== distEsmPath) {
    throw new Error(`import resolution mismatch: expected ${distEsmPath}, got ${resolvedImportPath}`)
  }
  if (resolvedImportCssPath !== distCssPath) {
    throw new Error(`import CSS resolution mismatch: expected ${distCssPath}, got ${resolvedImportCssPath}`)
  }
  if (resolvedRequirePath !== distCjsPath) {
    throw new Error(`require resolution mismatch: expected ${distCjsPath}, got ${resolvedRequirePath}`)
  }
  if (resolvedRequireCssPath !== distCssPath) {
    throw new Error(`require CSS resolution mismatch: expected ${distCssPath}, got ${resolvedRequireCssPath}`)
  }

  const summary = {
    generated_at: new Date().toISOString(),
    out_dir: outDir,
    package_name: packageJson.name,
    export_map: exportMap,
    dist_checks: distChecks,
    resolved_paths: {
      import_boring_ui: resolvedImportPath,
      import_boring_ui_css: resolvedImportCssPath,
      require_boring_ui: resolvedRequirePath,
      require_boring_ui_css: resolvedRequireCssPath,
    },
    passed: true,
  }

  const summaryPath = path.join(outDir, 'summary.json')
  await fs.writeFile(summaryPath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8')
  await appendLog(`[root-entrypoint-smoke] summary=${summaryPath}`)

  process.stdout.write(`[root-entrypoint-smoke] passed: ${summaryPath}\n`)
}

run().catch(async (error) => {
  const message = String(error?.stack || error)
  try {
    await fs.mkdir(outDir, { recursive: true })
    await appendLog(`[root-entrypoint-smoke] failed=${message}`)
    await fs.writeFile(
      path.join(outDir, 'summary.json'),
      `${JSON.stringify({
        generated_at: new Date().toISOString(),
        out_dir: outDir,
        passed: false,
        error: message,
      }, null, 2)}\n`,
      'utf8',
    )
  } catch {
    // best-effort artifact write only
  }
  console.error(error)
  process.exit(1)
})
