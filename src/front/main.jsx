import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ConfigProvider } from './config'
import './styles.css'

// Suppress known xterm.js renderer race condition errors during layout transitions.
const originalError = console.error
console.error = (...args) => {
  const msg = args[0]
  if (typeof msg === 'string' && msg.includes('_renderer.value is undefined')) {
    return
  }
  originalError.apply(console, args)
}

// Also catch unhandled errors for xterm renderer issues.
window.addEventListener('error', (event) => {
  if (event.message?.includes('_renderer.value is undefined')) {
    event.preventDefault()
    return false
  }
})

createRoot(document.getElementById('root')).render(
  <ConfigProvider>
    <App />
  </ConfigProvider>
)
