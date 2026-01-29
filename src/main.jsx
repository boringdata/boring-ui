import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/index.css'
import { configureStorage, migrateAllLegacyKeys } from './utils/storage'

// Configure storage with default prefix
// Apps can import and call configureStorage() with custom prefix before this file loads
// or use the config system to set storage.prefix
const storageConfig = window.__BORING_UI_CONFIG__?.storage || {}
if (storageConfig.prefix) {
  configureStorage({
    prefix: storageConfig.prefix,
    migrateLegacyKeys: storageConfig.migrateLegacyKeys,
  })
}

// Migrate legacy 'kurt-web-' keys to new prefix if configured
// This runs once on app load
if (storageConfig.prefix && storageConfig.prefix !== 'kurt-web') {
  const migrated = migrateAllLegacyKeys()
  if (migrated.length > 0) {
    console.info('[Storage] Migrated legacy keys:', migrated)
  }
}

// Suppress known xterm.js renderer race condition errors during layout transitions
// These occur when the terminal is destroyed while renderer is still initializing
const originalError = console.error
console.error = (...args) => {
  const msg = args[0]
  if (typeof msg === 'string' && msg.includes('_renderer.value is undefined')) {
    return // Suppress this specific xterm error
  }
  originalError.apply(console, args)
}

// Also catch unhandled errors for xterm renderer issues
window.addEventListener('error', (event) => {
  if (event.message?.includes('_renderer.value is undefined')) {
    event.preventDefault()
    return false
  }
})

createRoot(document.getElementById('root')).render(<App />)
