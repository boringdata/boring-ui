import { registerStatusRoutes } from './routes/status.js'
import { registerNotesRoutes } from './routes/notes.js'

export function createApp() {
  const app = {
    routes: [],
    get(path, handler) {
      this.routes.push({ method: 'GET', path, handler })
    },
    post(path, handler) {
      this.routes.push({ method: 'POST', path, handler })
    },
    delete(path, handler) {
      this.routes.push({ method: 'DELETE', path, handler })
    },
    listen() {
      return undefined
    },
  }
  registerStatusRoutes(app)
  registerNotesRoutes(app)
  return app
}

const app = createApp()
app.listen()
