const PROVIDER_ENV_KEYS = {
  anthropic: ['VITE_PI_ANTHROPIC_API_KEY', 'ANTHROPIC_API_KEY'],
  openai: ['VITE_PI_OPENAI_API_KEY', 'OPENAI_API_KEY'],
  google: ['VITE_PI_GOOGLE_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY'],
  'google-vertex': [
    'VITE_PI_GOOGLE_API_KEY',
    'GOOGLE_CLOUD_PROJECT',
    'GCLOUD_PROJECT',
    'GOOGLE_CLOUD_LOCATION',
  ],
}

function readEnvValue(key) {
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env && key in import.meta.env) {
      const value = String(import.meta.env[key] || '').trim()
      if (value) return value
    }
  } catch {
    // Ignore missing import.meta environments.
  }

  try {
    const processEnv = globalThis.process?.env
    if (processEnv && key in processEnv) {
      const value = String(processEnv[key] || '').trim()
      if (value) return value
    }
  } catch {
    // Ignore missing process environments.
  }

  return ''
}

export function getEnvApiKey(provider) {
  const normalizedProvider = String(provider || '').trim()
  if (!normalizedProvider) return undefined

  if (normalizedProvider === 'anthropic') {
    return readEnvValue('ANTHROPIC_OAUTH_TOKEN') || readEnvValue('VITE_PI_ANTHROPIC_API_KEY') || readEnvValue('ANTHROPIC_API_KEY') || undefined
  }

  if (normalizedProvider === 'github-copilot') {
    return readEnvValue('COPILOT_GITHUB_TOKEN') || readEnvValue('GH_TOKEN') || readEnvValue('GITHUB_TOKEN') || undefined
  }

  if (normalizedProvider === 'amazon-bedrock') {
    const hasCredentials = Boolean(
      readEnvValue('AWS_PROFILE')
      || (readEnvValue('AWS_ACCESS_KEY_ID') && readEnvValue('AWS_SECRET_ACCESS_KEY'))
      || readEnvValue('AWS_BEARER_TOKEN_BEDROCK')
      || readEnvValue('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI')
      || readEnvValue('AWS_CONTAINER_CREDENTIALS_FULL_URI')
      || readEnvValue('AWS_WEB_IDENTITY_TOKEN_FILE')
    )
    return hasCredentials ? '<authenticated>' : undefined
  }

  if (normalizedProvider === 'google-vertex') {
    const hasProject = Boolean(readEnvValue('GOOGLE_CLOUD_PROJECT') || readEnvValue('GCLOUD_PROJECT'))
    const hasLocation = Boolean(readEnvValue('GOOGLE_CLOUD_LOCATION'))
    const hasCredentials = Boolean(readEnvValue('VITE_PI_GOOGLE_API_KEY') || readEnvValue('GOOGLE_APPLICATION_CREDENTIALS'))
    return hasCredentials && hasProject && hasLocation ? '<authenticated>' : undefined
  }

  const keys = PROVIDER_ENV_KEYS[normalizedProvider] || []
  for (const key of keys) {
    const value = readEnvValue(key)
    if (value) return value
  }

  return undefined
}
