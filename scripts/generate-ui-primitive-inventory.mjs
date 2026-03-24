#!/usr/bin/env node

import fs from 'node:fs/promises'
import path from 'node:path'
import typescript from 'typescript'

const ts = typescript?.default ?? typescript

const DEFAULT_SOURCE_DIRS = [
  'src/front/components',
  'src/front/panels',
  'src/front/pages',
]
const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
const DEFAULT_OUT_DIR = process.env.OUT_DIR || path.join(process.cwd(), 'artifacts', 'ui-inventory')
const DEFAULT_OUT_FILE = process.env.OUT_FILE || `primitive-usage-${timestamp}.json`
const DEFAULT_SUMMARY_FILE = process.env.OUT_SUMMARY_FILE || `primitive-usage-${timestamp}.md`

const args = process.argv.slice(2)

const readArg = (name, fallback = '') => {
  const idx = args.indexOf(name)
  if (idx === -1 || idx + 1 >= args.length) return fallback
  return args[idx + 1]
}

const basePath = process.cwd()
const outDir = readArg('--out-dir', DEFAULT_OUT_DIR)
const outFileName = readArg('--out-file', DEFAULT_OUT_FILE)
const summaryFileName = readArg('--summary-file', DEFAULT_SUMMARY_FILE)
const sourceArg = readArg('--src', DEFAULT_SOURCE_DIRS.join(','))
const sourceDirs = sourceArg
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean)

const isCodeFile = (fileName) => ['.js', '.jsx', '.ts', '.tsx'].includes(path.extname(fileName))

const toRelativePosix = (absolutePath) => (
  path.relative(basePath, absolutePath).split(path.sep).join('/')
)

const ensureDir = async (directory) => {
  await fs.mkdir(directory, { recursive: true })
}

const collectFiles = async (directory) => {
  const absoluteDir = path.resolve(basePath, directory)
  let stats
  try {
    stats = await fs.stat(absoluteDir)
  } catch {
    return []
  }
  if (!stats.isDirectory()) return []

  const out = []
  const visit = async (current) => {
    const entries = await fs.readdir(current, { withFileTypes: true })
    entries.sort((left, right) => left.name.localeCompare(right.name))
    for (const entry of entries) {
      const absoluteEntry = path.join(current, entry.name)
      if (entry.isDirectory()) {
        // eslint-disable-next-line no-await-in-loop
        await visit(absoluteEntry)
        continue
      }
      if (entry.isFile() && isCodeFile(entry.name)) {
        out.push(absoluteEntry)
      }
    }
  }

  await visit(absoluteDir)
  return out
}

const incrementCount = (targetMap, key, amount = 1) => {
  targetMap.set(key, (targetMap.get(key) || 0) + amount)
}

const mapToSortedEntries = (mapObj) => (
  Array.from(mapObj.entries())
    .sort((left, right) => (
      right[1] - left[1] || left[0].localeCompare(right[0])
    ))
    .map(([name, count]) => ({ name, count }))
)

const listTop = (entries, limit = 20) => entries.slice(0, limit)

const toScriptKind = (fileName) => {
  const extension = path.extname(fileName).toLowerCase()
  if (extension === '.tsx') return ts.ScriptKind.TSX
  if (extension === '.ts') return ts.ScriptKind.TS
  if (extension === '.jsx') return ts.ScriptKind.JSX
  return ts.ScriptKind.JS
}

const classifyTag = (tagName) => {
  if (!tagName) return 'unknown'
  return /^[a-z]/.test(tagName) ? 'html' : 'component'
}

const renderSummaryMarkdown = (payload) => {
  const lines = []
  lines.push('# UI Primitive Inventory')
  lines.push('')
  lines.push(`Generated: ${payload.generated_at}`)
  lines.push(`Files scanned: ${payload.totals.files_scanned}`)
  lines.push(`JSX elements: ${payload.totals.jsx_elements}`)
  lines.push('')
  lines.push('## Source Dirs')
  lines.push('')
  payload.source_dirs.forEach((dir) => lines.push(`- \`${dir}\``))
  lines.push('')

  lines.push('## Top Component Tags')
  lines.push('')
  lines.push('| Tag | Count |')
  lines.push('| --- | ---: |')
  listTop(payload.tags.components, 30).forEach((entry) => {
    lines.push(`| \`${entry.name}\` | ${entry.count} |`)
  })
  lines.push('')

  lines.push('## Top HTML Tags')
  lines.push('')
  lines.push('| Tag | Count |')
  lines.push('| --- | ---: |')
  listTop(payload.tags.html, 30).forEach((entry) => {
    lines.push(`| \`${entry.name}\` | ${entry.count} |`)
  })
  lines.push('')

  lines.push('## Top Import Sources')
  lines.push('')
  lines.push('| Import | Count |')
  lines.push('| --- | ---: |')
  listTop(payload.imports, 30).forEach((entry) => {
    lines.push(`| \`${entry.name}\` | ${entry.count} |`)
  })
  lines.push('')

  lines.push('## Top Files By JSX Nodes')
  lines.push('')
  lines.push('| File | JSX nodes |')
  lines.push('| --- | ---: |')
  listTop(payload.files, 25).forEach((entry) => {
    lines.push(`| \`${entry.file}\` | ${entry.jsx_nodes} |`)
  })
  lines.push('')

  return `${lines.join('\n')}\n`
}

const run = async () => {
  await ensureDir(outDir)

  const globalComponentTags = new Map()
  const globalHtmlTags = new Map()
  const globalImportSources = new Map()
  const fileSummaries = []

  const allFiles = (
    await Promise.all(sourceDirs.map((dir) => collectFiles(dir)))
  )
    .flat()
    .sort((left, right) => left.localeCompare(right))

  let totalJsxNodes = 0

  for (const absoluteFile of allFiles) {
    // eslint-disable-next-line no-await-in-loop
    const sourceText = await fs.readFile(absoluteFile, 'utf8')
    const sourceFile = ts.createSourceFile(
      absoluteFile,
      sourceText,
      ts.ScriptTarget.Latest,
      true,
      toScriptKind(absoluteFile),
    )

    const localComponentTags = new Map()
    const localHtmlTags = new Map()
    const localImportSources = new Map()
    let jsxNodeCount = 0

    const walk = (node) => {
      if (ts.isImportDeclaration(node)) {
        const rawSpecifier = node.moduleSpecifier?.text
        if (rawSpecifier) {
          incrementCount(globalImportSources, rawSpecifier)
          incrementCount(localImportSources, rawSpecifier)
        }
      }

      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const rawTagName = node.tagName.getText(sourceFile)
        const tagName = rawTagName.trim()
        if (classifyTag(tagName) === 'html') {
          incrementCount(globalHtmlTags, tagName)
          incrementCount(localHtmlTags, tagName)
        } else {
          incrementCount(globalComponentTags, tagName)
          incrementCount(localComponentTags, tagName)
        }
        jsxNodeCount += 1
      }

      ts.forEachChild(node, walk)
    }

    walk(sourceFile)
    totalJsxNodes += jsxNodeCount

    fileSummaries.push({
      file: toRelativePosix(absoluteFile),
      jsx_nodes: jsxNodeCount,
      top_component_tags: listTop(mapToSortedEntries(localComponentTags), 10),
      top_html_tags: listTop(mapToSortedEntries(localHtmlTags), 10),
      top_import_sources: listTop(mapToSortedEntries(localImportSources), 10),
    })
  }

  fileSummaries.sort((left, right) => (
    right.jsx_nodes - left.jsx_nodes || left.file.localeCompare(right.file)
  ))

  const payload = {
    generated_at: new Date().toISOString(),
    source_dirs: sourceDirs,
    totals: {
      files_scanned: allFiles.length,
      jsx_elements: totalJsxNodes,
      unique_component_tags: globalComponentTags.size,
      unique_html_tags: globalHtmlTags.size,
      unique_import_sources: globalImportSources.size,
    },
    tags: {
      components: mapToSortedEntries(globalComponentTags),
      html: mapToSortedEntries(globalHtmlTags),
    },
    imports: mapToSortedEntries(globalImportSources),
    files: fileSummaries,
  }

  const outJsonPath = path.join(outDir, outFileName)
  const outSummaryPath = path.join(outDir, summaryFileName)

  await fs.writeFile(outJsonPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
  await fs.writeFile(outSummaryPath, renderSummaryMarkdown(payload), 'utf8')

  console.log(`UI primitive inventory written:`)
  console.log(`- ${toRelativePosix(outJsonPath)}`)
  console.log(`- ${toRelativePosix(outSummaryPath)}`)
  console.log(`Scanned files: ${payload.totals.files_scanned}`)
  console.log(`Total JSX nodes: ${payload.totals.jsx_elements}`)
}

run().catch((error) => {
  console.error(error)
  process.exit(1)
})
