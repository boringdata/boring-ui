import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_URL || 'http://localhost:8000'
  const proxyApiTarget = env.VITE_PROXY_API_TARGET || apiTarget
  const toWsTarget = (value: string) => value.replace(/^http(s?):\/\//i, 'ws$1://')
  const proxyWsTarget = toWsTarget(proxyApiTarget)
  // Workspace root for workspace plugin panel loading
  const workspaceRoot = env.BORING_UI_WORKSPACE_ROOT || env.WORKSPACE_ROOT || ''

  // Library build mode (npm run build:lib)
  const isLibMode = mode === 'lib'
  const resolveAlias = [
    { find: /^@\//, replacement: `${path.resolve(__dirname, './src/front')}/` },
    // Path aliases for shared + layouts
    { find: '@shared', replacement: path.resolve(__dirname, './src/front/shared') },
    { find: '@layouts', replacement: path.resolve(__dirname, './src/front/layouts') },
    {
      find: '@mariozechner/pi-ai/dist/providers/register-builtins.js',
      replacement: path.resolve(__dirname, './src/front/shared/providers/pi/registerBuiltins.browser.js'),
    },
    {
      find: '@mariozechner/pi-ai/dist/env-api-keys.js',
      replacement: path.resolve(__dirname, './src/front/shared/providers/pi/envApiKeys.browser.js'),
    },
    {
      find: '@mariozechner/pi-ai/dist/utils/http-proxy.js',
      replacement: path.resolve(__dirname, './src/front/shared/providers/pi/httpProxy.noop.js'),
    },
    {
      find: /^@mariozechner\/pi-ai$/,
      replacement: path.resolve(__dirname, './src/front/shared/providers/pi/piAi.browser.js'),
    },
    {
      find: /^node:zlib$/,
      replacement: path.resolve(__dirname, './src/front/shared/providers/data/nodeZlib.browser.js'),
    },
    {
      find: /^node:fs$/,
      replacement: path.resolve(__dirname, './src/front/shared/providers/data/nodeFs.browser.js'),
    },
    {
      find: /^node:os$/,
      replacement: path.resolve(__dirname, './src/front/shared/providers/data/nodeOs.browser.js'),
    },
    {
      find: /^node:path$/,
      replacement: path.resolve(__dirname, './src/front/shared/providers/data/nodePath.browser.js'),
    },
  ]
  if (workspaceRoot) {
    resolveAlias.push({
      find: '@workspace',
      replacement: path.resolve(workspaceRoot, 'kurt/panels'),
    })
  }

  const baseConfig = {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: resolveAlias,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      css: true,
      include: ['src/**/*.test.{js,jsx,ts,tsx}'],
    },
  }

  // Library build configuration
  if (isLibMode) {
    return {
      ...baseConfig,
      build: {
        lib: {
          entry: path.resolve(__dirname, 'src/front/index.js'),
          name: 'BoringUI',
          formats: ['es', 'cjs'],
          fileName: (format) => `boring-ui.${format === 'es' ? 'js' : 'cjs'}`,
        },
        rollupOptions: {
          // Externalize peer dependencies
          external: ['react', 'react-dom', 'react/jsx-runtime'],
          output: {
            // Global variable names for UMD build (not used but good practice)
            globals: {
              react: 'React',
              'react-dom': 'ReactDOM',
              'react/jsx-runtime': 'jsxRuntime',
            },
          },
        },
        cssCodeSplit: false, // Emit single style.css
        sourcemap: true,
      },
    }
  }

  // Anthropic API key for dev proxy
  const anthropicKey = env.ANTHROPIC_API_KEY || env.VITE_PI_ANTHROPIC_API_KEY || ''

  // Mock API plugin for standalone dev (no backend).
  // Mocks are FALLBACK-only: they check if the real backend is reachable
  // before serving stubs so they don't shadow a running server.
  let _backendReachable: boolean | null = null
  let _backendCheckTime = 0
  const RECHECK_MS = 10_000
  const isBackendReachable = async (): Promise<boolean> => {
    const now = Date.now()
    if (_backendReachable !== null && now - _backendCheckTime < RECHECK_MS) return _backendReachable
    _backendCheckTime = now
    try {
      const res = await fetch(`${proxyApiTarget}/health`, { signal: AbortSignal.timeout(500) })
      _backendReachable = res.ok
    } catch {
      _backendReachable = false
    }
    return _backendReachable
  }

  const mockApiPlugin = {
    name: 'mock-api',
    configureServer(server) {
      server.middlewares.use('/api/capabilities', async (_req, res, next) => {
        if (await isBackendReachable()) return next()
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({
          version: 'static-local',
          features: { files: true, git: true, pi: true },
          routers: [],
        }))
      })
      // Mock file API — serves files from the workspace for the Surface viewer
      server.middlewares.use('/api/file', async (req, res, next) => {
        if (await isBackendReachable()) return next()
        const url = new URL(req.url || '/', 'http://localhost')
        const filePath = url.searchParams.get('path')
        if (!filePath) { res.statusCode = 400; res.end('Missing path'); return }
        const fs = await import('fs')
        const path = await import('path')
        const fullPath = path.default.resolve(process.cwd(), filePath)
        // Security: only serve files within the project
        if (!fullPath.startsWith(process.cwd())) { res.statusCode = 403; res.end('Forbidden'); return }
        try {
          const content = fs.default.readFileSync(fullPath, 'utf-8')
          res.setHeader('Content-Type', 'text/plain')
          res.end(content)
        } catch (err) {
          res.statusCode = 404; res.end(`File not found: ${filePath}`)
        }
      })

      // Mock file tree API — lists directory contents
      server.middlewares.use('/api/tree', async (req, res, next) => {
        if (await isBackendReachable()) return next()
        const url = new URL(req.url || '/', 'http://localhost')
        const dirPath = url.searchParams.get('path') || '.'
        const fs = await import('fs')
        const path = await import('path')
        const fullPath = path.default.resolve(process.cwd(), dirPath)
        if (!fullPath.startsWith(process.cwd())) { res.statusCode = 403; res.end('Forbidden'); return }
        try {
          const entries = fs.default.readdirSync(fullPath, { withFileTypes: true })
            .filter(e => !e.name.startsWith('.') && e.name !== 'node_modules' && e.name !== 'dist')
            .map(e => ({ name: e.name, path: path.default.join(dirPath === '.' ? '' : dirPath, e.name), is_dir: e.isDirectory() }))
            .sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1))
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(entries))
        } catch { res.statusCode = 404; res.end('[]') }
      })

      // Anthropic streaming proxy for chat
      server.middlewares.use('/api/anthropic', async (req, res, next) => {
        if (await isBackendReachable()) return next()
        if (req.method !== 'POST') { res.statusCode = 405; res.end(); return }
        let body = ''
        for await (const chunk of req) body += chunk
        try {
          const upstream = await fetch('https://api.anthropic.com' + req.url.replace('/api/anthropic', ''), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'x-api-key': anthropicKey,
              'anthropic-version': '2023-06-01',
            },
            body,
          })
          res.statusCode = upstream.status
          // Only forward safe headers — skip content-encoding to avoid decompression issues
          res.setHeader('Content-Type', upstream.headers.get('content-type') || 'application/json')
          res.setHeader('Cache-Control', 'no-cache')
          if (upstream.headers.get('content-type')?.includes('event-stream')) {
            res.setHeader('Connection', 'keep-alive')
          }
          const reader = upstream.body.getReader()
          const pump = async () => {
            while (true) {
              const { done, value } = await reader.read()
              if (done) { res.end(); return }
              res.write(value)
            }
          }
          await pump()
        } catch (err) {
          res.statusCode = 502
          res.end(JSON.stringify({ error: String(err.message) }))
        }
      })
    },
  }

  // Development/app build configuration
  return {
    ...baseConfig,
    plugins: [...baseConfig.plugins, mockApiPlugin],
    define: {
      // Inject API keys so pi-ai's getEnvApiKey() can read them in browser
      'process.env.ANTHROPIC_API_KEY': JSON.stringify(env.VITE_PI_ANTHROPIC_API_KEY || env.ANTHROPIC_API_KEY || ''),
      'process.env.OPENAI_API_KEY': JSON.stringify(env.VITE_PI_OPENAI_API_KEY || ''),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.VITE_PI_GOOGLE_API_KEY || ''),
    },
    base: '/',
    build: {
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            // Split heavy vendor libraries into separate cacheable chunks
            if (id.includes('node_modules/@tiptap/') || id.includes('node_modules/lowlight/') || id.includes('node_modules/highlight.js/')) {
              return 'vendor-editor'
            }
            if (id.includes('node_modules/xterm')) {
              return 'vendor-terminal'
            }
            if (id.includes('node_modules/@mariozechner/')) {
              return 'vendor-pi'
            }
            if (id.includes('node_modules/@assistant-ui/') || id.includes('node_modules/markdown-it') || id.includes('node_modules/remark') || id.includes('node_modules/unified') || id.includes('node_modules/mdast') || id.includes('node_modules/micromark')) {
              return 'vendor-chat'
            }
            if (id.includes('node_modules/isomorphic-git')) {
              return 'vendor-git'
            }
            if (id.includes('node_modules/dockview')) {
              return 'vendor-dockview'
            }
            if (id.includes('node_modules/react-pdf') || id.includes('node_modules/pdfjs-dist')) {
              return 'vendor-pdf'
            }
          },
        },
      },
    },
    server: {
      port: 5173,
      watch: {
        // This repo is large; fs.watch can exceed inotify limits in local/dev containers.
        usePolling: true,
        interval: 1000,
        // Keep Vite focused on source files; large workspace folders can exceed inotify limits.
        ignored: [
          '**/.claude/**',
          '**/.beads/**',
          '**/.beads.old/**',
          '**/.agent-evidence/**',
          '**/.boring/**',
          '**/.evidence/**',
          '**/.bsw/**',
          '**/.venv/**',
          '**/artifacts/**',
          '**/flows/**',
          '**/playwright-report/**',
          '**/test-results/**',
          '**/dist/**',
          '**/vendor/**',
          '**/tests/**',
          '**/examples/**',
          '**/docs/**',
          '**/deploy/**',
        ],
      },
      fs: {
        allow: ['.', ...(workspaceRoot ? [workspaceRoot] : [])],
      },
      proxy: {
        '/__bui': {
          target: proxyApiTarget,
          changeOrigin: false,
        },
        '/api': {
          target: proxyApiTarget,
          changeOrigin: false,
        },
        '/auth': {
          target: proxyApiTarget,
          changeOrigin: false,
          bypass(req) {
            const requestUrl = new URL(req.url || '/', 'http://localhost')
            const requestPath = requestUrl.pathname
            const hasLocalIdentity = requestUrl.searchParams.has('user_id')
              && requestUrl.searchParams.has('email')
            // Let SPA handle these auth pages; proxy all other auth routes to backend
            if (requestPath === '/auth/settings') return req.url
            if (requestPath?.startsWith('/auth/login') && !hasLocalIdentity) return req.url
            if (requestPath?.startsWith('/auth/signup')) return req.url
            if (requestPath?.startsWith('/auth/reset-password')) return req.url
            if (requestPath?.startsWith('/auth/callback') && !hasLocalIdentity) return req.url
          },
        },
        '/w': {
          target: proxyApiTarget,
          changeOrigin: false,
          bypass(req) {
            const requestPath = req.url?.split('?')[0] || ''
            // Let SPA handle workspace root, setup, and settings pages;
            // only proxy workspace-scoped backend routes (e.g. /w/{id}/api/...).
            if (/^\/w\/[^/]+\/?$/.test(requestPath)) return req.url
            if (/^\/w\/[^/]+\/setup\/?$/.test(requestPath)) return req.url
            if (/^\/w\/[^/]+\/settings\/?$/.test(requestPath)) return req.url
          },
        },
        '/ws': {
          target: proxyWsTarget,
          changeOrigin: false,
          ws: true,
        },
      },
    },
  }
})
