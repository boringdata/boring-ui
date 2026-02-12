import SandboxAdapter from './adapter'

export const config = {
  id: 'sandbox',
  label: 'Sandbox',
  component: SandboxAdapter,
  requiresCapabilities: ['sandbox'],
}

export default config
