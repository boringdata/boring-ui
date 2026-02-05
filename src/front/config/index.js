/**
 * App configuration module for boring-ui.
 *
 * @example
 * // In main.jsx
 * import { ConfigProvider } from './config'
 *
 * createRoot(document.getElementById('root')).render(
 *   <ConfigProvider>
 *     <App />
 *   </ConfigProvider>
 * )
 *
 * @example
 * // In any component
 * import { useConfig } from './config'
 *
 * function MyComponent() {
 *   const config = useConfig()
 *   return <h1>{config.branding.name}</h1>
 * }
 */

export {
  getConfig,
  getDefaultConfig,
  resetConfig,
  setConfig,
} from './appConfig'

export {
  ConfigProvider,
  useConfig,
  useConfigLoaded,
} from './ConfigProvider'
