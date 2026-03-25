/**
 * Server entry point.
 *
 * Usage:
 *   npm run server:dev     # tsx watch (development)
 *   npm run server:start   # node --import tsx (production-like)
 */
import { createApp } from './app.js'
import { loadConfig, validateConfig } from './config.js'

const config = loadConfig()

// Fail closed: crash on misconfiguration at startup, not at first request
try {
  validateConfig(config)
} catch (err) {
  console.error(err instanceof Error ? err.message : String(err))
  process.exit(1)
}

const app = createApp({ config, logger: true, skipValidation: true })

app.listen({ port: config.port, host: config.host }, (err, address) => {
  if (err) {
    app.log.error(err)
    process.exit(1)
  }
  app.log.info(`Server listening at ${address}`)
})
