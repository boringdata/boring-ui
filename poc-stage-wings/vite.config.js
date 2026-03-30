import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'
import path from 'path'

// Get Anthropic API key from Vault
let anthropicKey = ''
try {
  anthropicKey = execSync('vault kv get -field=api_key secret/agent/anthropic', { encoding: 'utf-8' }).trim()
} catch { /* fallback to env */ }

const __dirname = path.dirname(new URL(import.meta.url).pathname)

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Force all React imports (including @ai-sdk/react) to use the POC's React 19
      'react': path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
  define: {
    'import.meta.env.VITE_ANTHROPIC_API_KEY': JSON.stringify(anthropicKey || process.env.ANTHROPIC_API_KEY || ''),
  },
  server: {
    proxy: {
      '/api/anthropic': {
        target: 'https://api.anthropic.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/anthropic/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('x-api-key', anthropicKey)
            proxyReq.setHeader('anthropic-version', '2023-06-01')
            proxyReq.setHeader('anthropic-dangerous-direct-browser-access', 'true')
          })
        },
      },
    },
  },
})
