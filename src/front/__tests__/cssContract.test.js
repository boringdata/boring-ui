import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(__dirname, '../../..')

const readRepoFile = (relativePath) => (
  fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')
)

const readPackageJson = () => JSON.parse(readRepoFile('package.json'))

const assertOrderedSubstrings = (source, needles, contextLabel) => {
  let previousIndex = -1

  needles.forEach((needle) => {
    const index = source.indexOf(needle)
    if (index < 0) {
      throw new Error(`[${contextLabel}] Missing expected fragment: ${needle}`)
    }
    if (index <= previousIndex) {
      throw new Error(
        `[${contextLabel}] Import/order contract broken. "${needle}" appeared at ${index}, previous index was ${previousIndex}.`
      )
    }
    previousIndex = index
  })
}

describe('Root Package CSS Contract', () => {
  it('keeps the public style entrypoint export stable', () => {
    const packageJson = readPackageJson()
    expect(packageJson.exports?.['./style.css']).toBe('./dist/style.css')
  })

  it('keeps Phase 1 CSS exports intentionally narrow', () => {
    const packageJson = readPackageJson()
    const cssSubpathExports = Object.keys(packageJson.exports ?? {}).filter((key) => key.endsWith('.css'))

    expect(cssSubpathExports).toEqual(['./style.css'])
  })

  it('imports root styles from the frontend app entrypoint exactly once', () => {
    const mainEntry = readRepoFile('src/front/main.jsx')
    const importMatches = mainEntry.match(/import\s+['"]\.\/styles\.css['"]/g) || []
    expect(importMatches).toHaveLength(1)
  })

  it('preserves canonical root stylesheet import order', () => {
    const styles = readRepoFile('src/front/styles.css')
    assertOrderedSubstrings(
      styles,
      [
        "@import url('https://fonts.googleapis.com",
        "@import './styles/tokens.css';",
        "@import './styles/scrollbars.css';",
      ],
      'src/front/styles.css'
    )
  })

  it('keeps Tailwind tooling baseline pinned and dark mode selector contract intact', () => {
    const packageJson = readPackageJson()
    expect(packageJson.devDependencies?.tailwindcss).toBe('4.1.18')
    expect(packageJson.devDependencies?.['@tailwindcss/vite']).toBe('4.1.18')

    const tailwindConfig = readRepoFile('tailwind.config.js')
    expect(tailwindConfig).toContain("darkMode: 'selector'")
  })

  it('keeps preflight ownership in root CSS instead of Tailwind base directives', () => {
    const styles = readRepoFile('src/front/styles.css')
    expect(styles).not.toMatch(/@tailwind\s+base/i)
    expect(styles).not.toMatch(/@import\s+['"]tailwindcss['"]/i)
  })

  it('keeps key design token bridges available for host-loaded shared styling', () => {
    const tokens = readRepoFile('src/front/styles/tokens.css')

    const requiredTokens = [
      '--color-bg-primary',
      '--color-text-primary',
      '--font-sans',
      '--space-4',
      '--radius-sm',
      '--color-focus-ring',
    ]

    requiredTokens.forEach((tokenName) => {
      expect(tokens).toContain(tokenName)
    })
  })

  it('keeps theme bridge semantics in tokens.css', () => {
    const tokens = readRepoFile('src/front/styles/tokens.css')
    expect(tokens).toContain(':root {')
    expect(tokens).toContain('[data-theme="dark"] {')

    const requiredDarkOverrides = [
      '--color-background-primary',
      '--color-text-primary',
      '--color-accent-default',
      '--color-focus-ring',
    ]

    const darkThemeBlock = tokens.match(/\[data-theme="dark"\]\s*{([\s\S]*?)\n}/)?.[1] ?? ''

    requiredDarkOverrides.forEach((tokenName) => {
      expect(darkThemeBlock).toContain(tokenName)
    })
  })

  it('keeps theme application wired to document root data-theme attribute', () => {
    const themeHook = readRepoFile('src/front/hooks/useTheme.jsx')
    expect(themeHook).toContain("document.documentElement.setAttribute('data-theme', theme)")
  })

  it('documents css and theme consumer expectations in runbook and README', () => {
    const runbook = readRepoFile('docs/runbooks/CSS_CONTRACT.md')
    const readme = readRepoFile('README.md')

    expect(runbook).toContain('keep `./style.css` as the only public CSS subpath export')
    expect(runbook).toContain('`tokens.css` is the canonical theme bridge')
    expect(runbook).toContain('runtime and child panels assume host-loaded shared UI CSS and token bridge')

    expect(readme).toContain('public CSS entrypoint remains `boring-ui/style.css`')
    expect(readme).toContain('Phase 1 exposes only one public CSS subpath export')
  })
})
