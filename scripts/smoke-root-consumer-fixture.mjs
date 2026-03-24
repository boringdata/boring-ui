/* global process, console */
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')
const packageJsonPath = path.join(repoRoot, 'package.json')
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'))

const ts = new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-')
const outDir = path.join(repoRoot, 'artifacts', 'root-consumer-smoke', ts)
const fixtureDir = path.join(outDir, 'fixture-consumer')
const fixtureSrcDir = path.join(fixtureDir, 'src')
const buildLogPath = path.join(outDir, 'build.log')
const summaryPath = path.join(outDir, 'summary.json')

fs.mkdirSync(fixtureSrcDir, { recursive: true })
fs.writeFileSync(buildLogPath, '')

const appendLog = (label, text) => {
  fs.appendFileSync(buildLogPath, `\n[${label}]\n${text ?? ''}\n`)
}

const run = (label, cmd, args, cwd) => {
  appendLog(label, `$ ${cmd} ${args.join(' ')}`)
  const result = spawnSync(cmd, args, {
    cwd,
    encoding: 'utf8',
    env: { ...process.env },
    maxBuffer: 64 * 1024 * 1024,
  })
  appendLog(`${label}:stdout`, result.stdout)
  appendLog(`${label}:stderr`, result.stderr)
  appendLog(`${label}:exit`, String(result.status))
  appendLog(`${label}:signal`, String(result.signal))
  if (result.error) {
    appendLog(
      `${label}:error`,
      JSON.stringify(
        {
          name: result.error.name,
          code: result.error.code,
          message: result.error.message,
        },
        null,
        2
      )
    )
  }

  if (result.error || result.status !== 0 || result.signal) {
    const statusDetail = result.signal
      ? `signal ${result.signal}`
      : `exit code ${result.status}`
    const error = new Error(`${label} failed with ${statusDetail}`)
    error.result = result
    throw error
  }
}

const writeFixtureFiles = () => {
  const fixturePackageJson = {
    name: 'boring-ui-smoke-consumer',
    private: true,
    version: '0.0.0',
    type: 'module',
    scripts: {
      build: 'vite build --logLevel error',
    },
    dependencies: {
      'boring-ui': `file:${repoRoot}`,
      react: packageJson.peerDependencies?.react || '18.2.0',
      'react-dom': packageJson.peerDependencies?.['react-dom'] || '18.2.0',
    },
    devDependencies: {
      vite: packageJson.devDependencies?.vite || '^5.0.0',
    },
  }

  fs.writeFileSync(
    path.join(fixtureDir, 'package.json'),
    `${JSON.stringify(fixturePackageJson, null, 2)}\n`
  )

  fs.writeFileSync(
    path.join(fixtureDir, 'index.html'),
    [
      '<!doctype html>',
      '<html>',
      '  <head><meta charset="UTF-8"><title>consumer-smoke</title></head>',
      '  <body>',
      '    <div id="app"></div>',
      '    <script type="module" src="/src/main.js"></script>',
      '  </body>',
      '</html>',
      '',
    ].join('\n')
  )

  fs.writeFileSync(
    path.join(fixtureSrcDir, 'main.js'),
    [
      "import 'boring-ui/style.css'",
      "import { cn, Button } from 'boring-ui'",
      "console.log('[consumer-smoke] cn', cn('p-2', 'p-4'))",
      "console.log('[consumer-smoke] button', Boolean(Button))",
      '',
    ].join('\n')
  )
}

const resolveFixtureImports = () => {
  const fixtureRequire = createRequire(path.join(fixtureDir, 'package.json'))
  const rootPath = fixtureRequire.resolve('boring-ui')
  const cssPath = fixtureRequire.resolve('boring-ui/style.css')
  const pkgPath = path.resolve(path.dirname(rootPath), '..', 'package.json')
  return { pkgPath, cssPath, rootPath }
}

const runSmoke = () => {
  run('build-lib', 'npm', ['run', 'build:lib'], repoRoot)
  writeFixtureFiles()
  run('fixture-install', 'npm', ['install'], fixtureDir)
  const resolved = resolveFixtureImports()
  appendLog('fixture-resolve', JSON.stringify(resolved, null, 2))
  run('fixture-build', 'npm', ['run', 'build'], fixtureDir)

  const distDir = path.join(fixtureDir, 'dist')
  const files = fs.existsSync(distDir) ? fs.readdirSync(distDir) : []
  const hasIndexHtml = files.includes('index.html')

  const assetsDir = path.join(distDir, 'assets')
  const assets = fs.existsSync(assetsDir) ? fs.readdirSync(assetsDir) : []
  const hasCssAsset = assets.some((name) => name.endsWith('.css'))
  const hasJsAsset = assets.some((name) => name.endsWith('.js'))

  const summary = {
    generated_at: new Date().toISOString(),
    out_dir: outDir,
    fixture_dir: fixtureDir,
    package_name: packageJson.name,
    resolved,
    checks: {
      has_index_html: hasIndexHtml,
      has_css_asset: hasCssAsset,
      has_js_asset: hasJsAsset,
    },
    passed: hasIndexHtml && hasCssAsset && hasJsAsset,
  }

  fs.writeFileSync(summaryPath, `${JSON.stringify(summary, null, 2)}\n`)
  console.log(`[root-consumer-smoke] ${summary.passed ? 'passed' : 'failed'}: ${summaryPath}`)

  if (!summary.passed) {
    process.exit(1)
  }
}

try {
  runSmoke()
} catch (error) {
  appendLog('fatal', error?.stack || String(error))
  fs.writeFileSync(
    summaryPath,
    `${JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        out_dir: outDir,
        passed: false,
        error: error?.message || String(error),
      },
      null,
      2
    )}\n`
  )
  console.error(`[root-consumer-smoke] failed: ${summaryPath}`)
  process.exit(1)
}
