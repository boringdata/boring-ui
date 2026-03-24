#!/usr/bin/env node

import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const repoRoot = process.cwd()
const frontRoot = path.join(repoRoot, 'src/front')
const pagesRoot = path.join(frontRoot, 'pages')
const stylesPath = path.join(frontRoot, 'styles.css')

const sourceExtensions = new Set(['.js', '.jsx', '.ts', '.tsx'])

const retiredClassTokens = new Set([
  'btn',
  'btn-primary',
  'btn-secondary',
  'btn-ghost',
  'btn-icon',
])

const retiredCssSelectors = [
  { selector: '.btn', pattern: /^\.btn\s*\{/m },
  { selector: '.btn-primary', pattern: /^\.btn-primary\s*\{/m },
  { selector: '.btn-secondary', pattern: /^\.btn-secondary\s*\{/m },
  { selector: '.btn-ghost', pattern: /^\.btn-ghost\s*\{/m },
  { selector: '.btn-icon', pattern: /^\.btn-icon\s*\{/m },
  { selector: '.modal-overlay', pattern: /^\.modal-overlay\s*\{/m },
]

const primitiveWrapperPattern = /\b(?:const|function)\s+([A-Z][A-Za-z0-9]*(?:Button|Input|Textarea|Select|Dialog|Dropdown|Tooltip|Avatar|Tabs|Separator|Badge))\b/g

const classAttrPatterns = [
  /className\s*=\s*"([^"]*)"/g,
  /className\s*=\s*'([^']*)'/g,
  /className\s*=\s*\{`([^`]*)`\}/g,
]

function toLine(content, index) {
  return content.slice(0, index).split('\n').length
}

async function walk(dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(dirPath, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__') return []
      return walk(absolutePath)
    }
    return [absolutePath]
  }))
  return files.flat()
}

function scanClassNames(filePath, content) {
  const violations = []
  for (const pattern of classAttrPatterns) {
    pattern.lastIndex = 0
    let match = pattern.exec(content)
    while (match) {
      const rawClassValue = match[1].replace(/\$\{[^}]*\}/g, ' ')
      const tokens = rawClassValue.split(/\s+/).filter(Boolean)
      for (const token of tokens) {
        if (retiredClassTokens.has(token)) {
          violations.push({
            filePath,
            line: toLine(content, match.index),
            reason: `retired class token "${token}"`,
          })
        }
      }
      match = pattern.exec(content)
    }
  }
  return violations
}

function scanPageLocalPrimitiveWrappers(filePath, content) {
  const violations = []
  primitiveWrapperPattern.lastIndex = 0
  let match = primitiveWrapperPattern.exec(content)
  while (match) {
    violations.push({
      filePath,
      line: toLine(content, match.index),
      reason: `page-local primitive wrapper "${match[1]}"`,
    })
    match = primitiveWrapperPattern.exec(content)
  }
  return violations
}

function printViolations(violations) {
  console.error('Phase 1 guardrail violations:')
  for (const violation of violations) {
    const relativePath = path.relative(repoRoot, violation.filePath)
    console.error(`- ${relativePath}:${violation.line} ${violation.reason}`)
  }
}

async function run() {
  const violations = []
  const sourceFiles = (await walk(frontRoot))
    .filter((filePath) => sourceExtensions.has(path.extname(filePath)))

  for (const filePath of sourceFiles) {
    const content = await fs.readFile(filePath, 'utf8')
    violations.push(...scanClassNames(filePath, content))
  }

  const pageFiles = (await walk(pagesRoot))
    .filter((filePath) => ['.js', '.jsx'].includes(path.extname(filePath)))

  for (const pageFile of pageFiles) {
    const content = await fs.readFile(pageFile, 'utf8')
    violations.push(...scanPageLocalPrimitiveWrappers(pageFile, content))
  }

  const stylesContent = await fs.readFile(stylesPath, 'utf8')
  for (const { selector, pattern } of retiredCssSelectors) {
    const match = pattern.exec(stylesContent)
    if (match) {
      violations.push({
        filePath: stylesPath,
        line: toLine(stylesContent, match.index),
        reason: `retired CSS selector "${selector}" still present`,
      })
    }
  }

  if (violations.length > 0) {
    printViolations(violations)
    process.exit(1)
  }

  console.log('Phase 1 guardrails: OK')
}

run().catch((error) => {
  console.error('Failed to run Phase 1 guardrail checks:', error)
  process.exit(1)
})
