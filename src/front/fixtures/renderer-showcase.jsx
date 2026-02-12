/**
 * Renderer Showcase — Deterministic fixture page for visual regression testing.
 *
 * Renders every shared tool renderer with known data, used by Playwright
 * to capture screenshots and compare against baselines.
 *
 * Served at /fixture-renderers.html in dev mode.
 */
import { createRoot } from 'react-dom/client'
import {
  BashRenderer,
  ReadRenderer,
  WriteRenderer,
  EditRenderer,
  GrepRenderer,
  GlobRenderer,
  GenericRenderer,
  ToolRendererProvider,
  ToolResultView,
  createToolResult,
} from '../shared/renderers'
import '../styles.css'
import '../shared/renderers/tool-use-block.css'

// ─── Fixture Data ────────────────────────────────────────────────────

const FIXTURES = {
  bash: {
    success: {
      command: 'ls -la src/',
      description: 'List files',
      output: 'total 32\ndrwxr-xr-x  8 user  staff  256 Jan 15 09:30 .\n-rw-r--r--  1 user  staff  1024 Jan 15 09:28 App.jsx\n-rw-r--r--  1 user  staff  512 Jan 15 09:20 main.jsx\n-rw-r--r--  1 user  staff  2048 Jan 15 09:15 styles.css',
      status: 'complete',
    },
    error: {
      command: 'cat /nonexistent/file.txt',
      description: 'cat /nonexistent/file.txt',
      error: 'cat: /nonexistent/file.txt: No such file or directory',
      exitCode: 1,
      status: 'error',
    },
    running: {
      command: 'npm install',
      description: 'npm install',
      status: 'running',
    },
    longOutput: {
      command: 'git log --oneline -20',
      description: 'git log --oneline -20',
      output: Array.from({ length: 20 }, (_, i) =>
        `${String(i + 1).padStart(2, '0')}a1b2c feat: commit message number ${i + 1}`,
      ).join('\n'),
      status: 'complete',
    },
  },

  read: {
    success: {
      filePath: 'src/front/App.jsx',
      content: '/**\n * Main application component.\n */\nimport { useState } from \'react\'\nimport Layout from \'./Layout\'\n\nexport default function App() {\n  const [theme, setTheme] = useState(\'dark\')\n  return <Layout theme={theme} />\n}',
      lineCount: 10,
      status: 'complete',
    },
    truncated: {
      filePath: 'package.json',
      content: '{\n  "name": "boring-ui",\n  "version": "1.0.0"\n  // ... truncated ...\n}',
      lineCount: 150,
      truncated: true,
      status: 'complete',
    },
    error: {
      filePath: 'missing.js',
      error: 'ENOENT: no such file or directory',
      status: 'error',
    },
  },

  write: {
    success: {
      filePath: 'src/config.js',
      content: 'export const API_URL = "http://localhost:8000"\nexport const WS_URL = "ws://localhost:8000"\nexport const VERSION = "1.0.0"',
      status: 'complete',
    },
    pending: {
      filePath: 'src/new-file.js',
      status: 'pending',
    },
  },

  edit: {
    diff: {
      filePath: 'src/App.jsx',
      diff: ' import { useState } from \'react\'\n-import OldComponent from \'./OldComponent\'\n+import NewComponent from \'./NewComponent\'\n+import { useEffect } from \'react\'\n \n export default function App() {\n-  return <OldComponent />\n+  return <NewComponent />',
      status: 'complete',
    },
    oldNew: {
      filePath: 'src/utils.js',
      oldContent: 'function calculateTotal(items) {\n  let total = 0\n  for (const item of items) {\n    total += item.price\n  }\n  return total\n}',
      newContent: 'function calculateTotal(items) {\n  return items.reduce((sum, item) => sum + item.price, 0)\n}',
      status: 'complete',
    },
    error: {
      filePath: 'src/readonly.js',
      error: 'Permission denied: file is read-only',
      status: 'error',
    },
  },

  grep: {
    success: {
      pattern: 'useState',
      path: 'src/',
      results: [
        {
          file: 'src/App.jsx',
          matches: [
            { line: 2, content: "import { useState } from 'react'" },
            { line: 5, content: '  const [theme, setTheme] = useState(\'dark\')' },
          ],
        },
        {
          file: 'src/components/Modal.jsx',
          matches: [
            { line: 1, content: "import { useState, useEffect } from 'react'" },
            { line: 8, content: '  const [isOpen, setIsOpen] = useState(false)' },
            { line: 9, content: '  const [content, setContent] = useState(null)' },
          ],
        },
      ],
      status: 'complete',
    },
    noResults: {
      pattern: 'nonExistentSymbol',
      path: 'src/',
      results: [],
      status: 'complete',
    },
    running: {
      pattern: 'TODO',
      status: 'running',
    },
  },

  glob: {
    success: {
      pattern: 'src/**/*.jsx',
      files: [
        'src/App.jsx',
        'src/main.jsx',
        'src/components/Modal.jsx',
        'src/components/Header.jsx',
        'src/components/FileTree.jsx',
        'src/panels/EditorPanel.jsx',
        'src/panels/TerminalPanel.jsx',
      ],
      status: 'complete',
    },
    noFiles: {
      pattern: '**/*.xyz',
      files: [],
      status: 'complete',
    },
  },

  generic: {
    success: {
      toolName: 'WebSearch',
      description: 'react vite configuration 2026',
      output: 'Found 15 results for "react vite configuration"...',
      status: 'complete',
    },
    running: {
      toolName: 'TaskCreate',
      description: 'Creating implementation plan',
      status: 'running',
    },
  },

  context: {
    viaContext: createToolResult({
      toolType: 'bash',
      toolName: 'Bash',
      description: 'echo "rendered via ToolResultView"',
      status: 'complete',
      input: { command: 'echo "rendered via ToolResultView"' },
      output: { content: 'rendered via ToolResultView' },
    }),
  },
}

// ─── Showcase Component ──────────────────────────────────────────────

function Section({ title, id, children }) {
  return (
    <section data-testid={`section-${id}`} style={{ marginBottom: '32px' }}>
      <h2 style={{ fontSize: '18px', marginBottom: '16px', color: 'var(--color-text-primary)' }}>
        {title}
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {children}
      </div>
    </section>
  )
}

function Fixture({ label, id, children }) {
  return (
    <div data-testid={`fixture-${id}`}>
      <div style={{ fontSize: '12px', color: 'var(--color-text-tertiary)', marginBottom: '4px' }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function RendererShowcase() {
  return (
    <ToolRendererProvider>
      <div
        data-testid="renderer-showcase"
        style={{
          maxWidth: '700px',
          margin: '0 auto',
          padding: '24px',
          fontFamily: 'var(--font-sans)',
          backgroundColor: 'var(--color-bg-primary)',
          color: 'var(--color-text-primary)',
          minHeight: '100vh',
        }}
      >
        <h1 style={{ fontSize: '24px', marginBottom: '32px' }}>
          Shared Tool Renderer Fixtures
        </h1>

        <Section title="Bash Renderer" id="bash">
          <Fixture label="Success with output" id="bash-success">
            <BashRenderer {...FIXTURES.bash.success} />
          </Fixture>
          <Fixture label="Error with exit code" id="bash-error">
            <BashRenderer {...FIXTURES.bash.error} />
          </Fixture>
          <Fixture label="Running state" id="bash-running">
            <BashRenderer {...FIXTURES.bash.running} />
          </Fixture>
          <Fixture label="Long output (truncated)" id="bash-long">
            <BashRenderer {...FIXTURES.bash.longOutput} />
          </Fixture>
        </Section>

        <Section title="Read Renderer" id="read">
          <Fixture label="File content" id="read-success">
            <ReadRenderer {...FIXTURES.read.success} />
          </Fixture>
          <Fixture label="Truncated file" id="read-truncated">
            <ReadRenderer {...FIXTURES.read.truncated} />
          </Fixture>
          <Fixture label="Error" id="read-error">
            <ReadRenderer {...FIXTURES.read.error} />
          </Fixture>
        </Section>

        <Section title="Write Renderer" id="write">
          <Fixture label="Written file" id="write-success">
            <WriteRenderer {...FIXTURES.write.success} />
          </Fixture>
          <Fixture label="Pending" id="write-pending">
            <WriteRenderer {...FIXTURES.write.pending} />
          </Fixture>
        </Section>

        <Section title="Edit Renderer" id="edit">
          <Fixture label="Diff view" id="edit-diff">
            <EditRenderer {...FIXTURES.edit.diff} />
          </Fixture>
          <Fixture label="Old/New content" id="edit-oldnew">
            <EditRenderer {...FIXTURES.edit.oldNew} />
          </Fixture>
          <Fixture label="Error" id="edit-error">
            <EditRenderer {...FIXTURES.edit.error} />
          </Fixture>
        </Section>

        <Section title="Grep Renderer" id="grep">
          <Fixture label="Search results" id="grep-success">
            <GrepRenderer {...FIXTURES.grep.success} />
          </Fixture>
          <Fixture label="No matches" id="grep-empty">
            <GrepRenderer {...FIXTURES.grep.noResults} />
          </Fixture>
          <Fixture label="Running" id="grep-running">
            <GrepRenderer {...FIXTURES.grep.running} />
          </Fixture>
        </Section>

        <Section title="Glob Renderer" id="glob">
          <Fixture label="File list" id="glob-success">
            <GlobRenderer {...FIXTURES.glob.success} />
          </Fixture>
          <Fixture label="No files" id="glob-empty">
            <GlobRenderer {...FIXTURES.glob.noFiles} />
          </Fixture>
        </Section>

        <Section title="Generic Renderer" id="generic">
          <Fixture label="Unknown tool" id="generic-success">
            <GenericRenderer {...FIXTURES.generic.success} />
          </Fixture>
          <Fixture label="Running" id="generic-running">
            <GenericRenderer {...FIXTURES.generic.running} />
          </Fixture>
        </Section>

        <Section title="ToolResultView (via Context)" id="context">
          <Fixture label="Rendered via ToolRendererProvider" id="context-view">
            <ToolResultView result={FIXTURES.context.viaContext} />
          </Fixture>
        </Section>
      </div>
    </ToolRendererProvider>
  )
}

// ─── Mount ───────────────────────────────────────────────────────────

const root = createRoot(document.getElementById('fixture-root'))
root.render(<RendererShowcase />)
