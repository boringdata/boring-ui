import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_URL || 'http://localhost:8000'
  const companionTarget = env.VITE_COMPANION_PROXY_TARGET
  // When using boring-sandbox gateway, set VITE_GATEWAY_URL=http://localhost:8080
  const gatewayTarget = env.VITE_GATEWAY_URL || apiTarget
  // Workspace root for workspace plugin panel loading
  const workspaceRoot = env.BORING_UI_WORKSPACE_ROOT || env.WORKSPACE_ROOT || ''

  // Library build mode (npm run build:lib)
  const isLibMode = mode === 'lib'

  const baseConfig = {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src/front'),
        ...(workspaceRoot ? { '@workspace': path.resolve(workspaceRoot, 'kurt/panels') } : {}),
      },
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

  // Development/app build configuration
  return {
    ...baseConfig,
    base: './',
    server: {
      port: 5173,
      fs: {
        allow: ['.', ...(workspaceRoot ? [workspaceRoot] : [])],
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
        ...(companionTarget
          ? {
              '/companion': {
                target: companionTarget,
                changeOrigin: true,
                ws: true,
                rewrite: (path: string) => path.replace(/^\/companion/, ''),
              },
            }
          : {}),
      },
    },
  }
})
