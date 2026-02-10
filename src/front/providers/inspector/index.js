import InspectorAdapter from './adapter'

export const config = {
  id: 'inspector',
  label: 'Inspector',
  component: InspectorAdapter,
  requiresCapabilities: ['sandbox'],
}

export default config
