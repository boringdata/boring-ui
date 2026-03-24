/* global process, console */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')

const readText = (relativePath) => (
  fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')
)

const readJson = (relativePath) => JSON.parse(readText(relativePath))

const failures = []

const expectEqual = (actual, expected, label) => {
  if (actual !== expected) {
    failures.push(`${label}: expected "${expected}", received "${actual}"`)
  }
}

const packageJson = readJson('package.json')
const componentsConfig = readJson('components.json')
const shadcnRunbook = readText('docs/runbooks/SHADCN_BASELINE.md')
const upstreamRunbook = readText('docs/runbooks/UPSTREAM_SHADCN.md')

const expectedVersions = {
  dependencies: {
    'lucide-react': '0.562.0',
    'tailwind-merge': '3.4.0',
  },
  devDependencies: {
    '@tailwindcss/vite': '4.1.18',
    tailwindcss: '4.1.18',
    'tw-animate-css': '1.4.0',
  },
}

Object.entries(expectedVersions.dependencies).forEach(([name, version]) => {
  expectEqual(packageJson.dependencies?.[name], version, `package.json dependencies.${name}`)
})

Object.entries(expectedVersions.devDependencies).forEach(([name, version]) => {
  expectEqual(packageJson.devDependencies?.[name], version, `package.json devDependencies.${name}`)
})

expectEqual(componentsConfig.style, 'new-york', 'components.json style')
expectEqual(componentsConfig.rsc, false, 'components.json rsc')
expectEqual(componentsConfig.tsx, false, 'components.json tsx')
expectEqual(componentsConfig.tailwind?.config, 'tailwind.config.js', 'components.json tailwind.config')
expectEqual(componentsConfig.tailwind?.css, 'src/front/styles.css', 'components.json tailwind.css')
expectEqual(componentsConfig.tailwind?.cssVariables, true, 'components.json tailwind.cssVariables')
expectEqual(componentsConfig.iconLibrary, 'lucide', 'components.json iconLibrary')

if (!shadcnRunbook.includes('npx --yes shadcn@4.1.0 init')) {
  failures.push('docs/runbooks/SHADCN_BASELINE.md must include pinned init command: npx --yes shadcn@4.1.0 init')
}

if (!shadcnRunbook.includes('npx --yes shadcn@4.1.0 add')) {
  failures.push('docs/runbooks/SHADCN_BASELINE.md must include pinned add command: npx --yes shadcn@4.1.0 add')
}

if (/@latest\b/.test(shadcnRunbook)) {
  failures.push('docs/runbooks/SHADCN_BASELINE.md must not use @latest')
}

if (/\bpnpm\b/.test(shadcnRunbook)) {
  failures.push('docs/runbooks/SHADCN_BASELINE.md must stay npm-only (no pnpm instructions)')
}

if (!upstreamRunbook.includes('## Generated From shadcn')) {
  failures.push('docs/runbooks/UPSTREAM_SHADCN.md is missing "Generated From shadcn" section')
}

if (!upstreamRunbook.includes('## Boring-ui Customizations')) {
  failures.push('docs/runbooks/UPSTREAM_SHADCN.md is missing "Boring-ui Customizations" section')
}

if (failures.length > 0) {
  console.error('[shadcn-baseline] FAIL')
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}

console.log('[shadcn-baseline] PASS')
