import CompanionAdapter from './adapter'

export const config = {
  id: 'companion',
  label: 'Companion',
  component: CompanionAdapter,
  requiresCapabilities: ['companion'],
}

export default config
