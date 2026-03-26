import { generateKeyPairSync } from 'node:crypto'
import { describe, it, expect, vi } from 'vitest'
import * as jose from 'jose'
import {
  createGitHubAppJwt,
  buildGitCredentials,
  buildOAuthUrl,
  isGitHubConfigured,
} from '../services/githubImpl.js'
import { loadConfig } from '../config.js'

// Generate a test RSA key pair for JWT signing tests
let testPrivateKeyPem: string
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let testPublicKey: any

async function ensureTestKeys() {
  if (testPrivateKeyPem) return
  const { privateKey, publicKey } = await jose.generateKeyPair('RS256', {
    extractable: true,
  })
  testPrivateKeyPem = await jose.exportPKCS8(privateKey)
  testPublicKey = publicKey
}

describe('GitHub App JWT signing (RS256)', () => {
  it('generates valid RS256 JWT with correct claims', async () => {
    await ensureTestKeys()
    const jwt = await createGitHubAppJwt('12345', testPrivateKeyPem)

    // Verify the JWT
    const { payload } = await jose.jwtVerify(jwt, testPublicKey, {
      algorithms: ['RS256'],
    })

    expect(payload.iss).toBe('12345')
    expect(payload.iat).toBeTypeOf('number')
    expect(payload.exp).toBeTypeOf('number')
    // exp should be ~10 minutes after iat
    expect(payload.exp! - payload.iat!).toBeLessThanOrEqual(670) // 600 + 60 clock drift
  })

  it('JWT has iat with clock drift allowance', async () => {
    await ensureTestKeys()
    const before = Math.floor(Date.now() / 1000) - 61
    const jwt = await createGitHubAppJwt('12345', testPrivateKeyPem)
    const { payload } = await jose.jwtVerify(jwt, testPublicKey, {
      algorithms: ['RS256'],
    })
    // iat should be now - 60s (drift allowance)
    expect(payload.iat!).toBeGreaterThanOrEqual(before)
  })

  it('rejects invalid PEM', async () => {
    await expect(
      createGitHubAppJwt('12345', 'not-a-valid-pem'),
    ).rejects.toThrow()
  })

  it('accepts PKCS#1 RSA private keys from Vault-style GitHub App PEMs', async () => {
    const { privateKey, publicKey } = generateKeyPairSync('rsa', {
      modulusLength: 2048,
    })
    const pkcs1Pem = privateKey.export({
      type: 'pkcs1',
      format: 'pem',
    }).toString()

    const jwt = await createGitHubAppJwt('12345', pkcs1Pem)
    const { payload } = await jose.jwtVerify(jwt, publicKey, {
      algorithms: ['RS256'],
    })

    expect(payload.iss).toBe('12345')
  })
})

describe('Git credential provisioning', () => {
  it('builds x-access-token credentials', () => {
    const creds = buildGitCredentials('ghs_abc123')
    expect(creds.username).toBe('x-access-token')
    expect(creds.password).toBe('ghs_abc123')
  })

  it('token appears in password field (not username)', () => {
    const creds = buildGitCredentials('ghs_secrettoken')
    expect(creds.username).not.toContain('ghs_secrettoken')
    expect(creds.password).toBe('ghs_secrettoken')
  })
})

describe('OAuth flow', () => {
  it('builds correct authorization URL', () => {
    const url = buildOAuthUrl(
      'Iv1.abc123',
      'https://myapp.com/callback',
      'state-xyz',
    )
    expect(url).toContain('github.com/login/oauth/authorize')
    expect(url).toContain('client_id=Iv1.abc123')
    expect(url).toContain('redirect_uri=https%3A%2F%2Fmyapp.com%2Fcallback')
    expect(url).toContain('state=state-xyz')
    expect(url).toContain('scope=read%3Auser')
  })

  it('URL-encodes special characters in redirect URI', () => {
    const url = buildOAuthUrl('id', 'https://app.com/auth?foo=bar', 'state')
    expect(url).toContain('redirect_uri=https%3A%2F%2Fapp.com%2Fauth%3Ffoo%3Dbar')
  })
})

describe('isGitHubConfigured', () => {
  it('returns false when app_id missing', () => {
    const config = { ...loadConfig(), githubAppId: undefined }
    expect(isGitHubConfigured(config)).toBe(false)
  })

  it('returns false when private key missing', () => {
    const config = { ...loadConfig(), githubAppId: '123', githubAppPrivateKey: undefined }
    expect(isGitHubConfigured(config)).toBe(false)
  })

  it('returns false when sync disabled', () => {
    const config = {
      ...loadConfig(),
      githubAppId: '123',
      githubAppPrivateKey: 'pem...',
      githubSyncEnabled: false,
    }
    expect(isGitHubConfigured(config)).toBe(false)
  })

  it('returns true when fully configured', () => {
    const config = {
      ...loadConfig(),
      githubAppId: '123',
      githubAppPrivateKey: 'pem...',
      githubSyncEnabled: true,
    }
    expect(isGitHubConfigured(config)).toBe(true)
  })
})
