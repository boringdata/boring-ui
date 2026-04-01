import { afterEach, describe, expect, it, vi } from 'vitest'

import { getEnvApiKey } from './envApiKeys.browser'

const originalProcess = globalThis.process

function setProcessEnv(env) {
  vi.stubGlobal('process', { env })
}

describe('envApiKeys.browser', () => {
  afterEach(() => {
    if (originalProcess) {
      vi.stubGlobal('process', originalProcess)
    } else {
      vi.unstubAllGlobals()
    }
  })

  it('reads provider keys from injected process env', () => {
    setProcessEnv({
      ANTHROPIC_API_KEY: 'anthropic-secret',
      OPENAI_API_KEY: 'openai-secret',
      GEMINI_API_KEY: 'google-secret',
    })

    expect(getEnvApiKey('anthropic')).toBe('anthropic-secret')
    expect(getEnvApiKey('openai')).toBe('openai-secret')
    expect(getEnvApiKey('google')).toBe('google-secret')
  })

  it('prefers anthropic oauth tokens over api keys', () => {
    setProcessEnv({
      ANTHROPIC_OAUTH_TOKEN: 'oauth-token',
      ANTHROPIC_API_KEY: 'anthropic-secret',
    })

    expect(getEnvApiKey('anthropic')).toBe('oauth-token')
  })

  it('reports authenticated for providers with non-key credential flows', () => {
    setProcessEnv({
      AWS_PROFILE: 'default',
      GOOGLE_CLOUD_PROJECT: 'demo-project',
      GOOGLE_CLOUD_LOCATION: 'us-central1',
      GOOGLE_APPLICATION_CREDENTIALS: '/tmp/fake-creds.json',
    })

    expect(getEnvApiKey('amazon-bedrock')).toBe('<authenticated>')
    expect(getEnvApiKey('google-vertex')).toBe('<authenticated>')
  })

  it('returns undefined when a provider has no configured credentials', () => {
    setProcessEnv({})

    expect(getEnvApiKey('anthropic')).toBeUndefined()
    expect(getEnvApiKey('unknown-provider')).toBeUndefined()
  })
})
