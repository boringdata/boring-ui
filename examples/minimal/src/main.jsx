import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, ThemeProvider } from 'boring-ui'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark">
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </ThemeProvider>
  </React.StrictMode>
)
