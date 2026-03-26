/**
 * GitHub App service implementation.
 * JWT signing (RS256), OAuth flow, installation token exchange.
 */
import { createPrivateKey } from 'node:crypto'
import * as jose from 'jose'
import type { ServerConfig } from '../config.js'

export interface GitHubCredentials {
  username: string
  password: string
}

export interface GitHubInstallation {
  id: number
  account: string
  account_type: string
  app_slug: string
}

export interface GitHubRepo {
  id: number
  full_name: string
  private: boolean
  clone_url: string
  ssh_url?: string
}

/**
 * Build the GitHub App installation URL.
 */
export function buildGitHubAppInstallationUrl(
  appSlug: string,
  state: string,
): string {
  const params = new URLSearchParams({ state })
  return `https://github.com/apps/${appSlug}/installations/new?${params.toString()}`
}

/**
 * Create a GitHub App JWT for API authentication.
 * Uses RS256 with the App's private key.
 */
export async function createGitHubAppJwt(
  appId: string,
  privateKeyPem: string,
): Promise<string> {
  const privateKey = createPrivateKey({
    key: privateKeyPem,
    format: 'pem',
  })
  const now = Math.floor(Date.now() / 1000)

  return new jose.SignJWT({})
    .setProtectedHeader({ alg: 'RS256' })
    .setIssuer(appId)
    .setIssuedAt(now - 60) // 60s clock drift allowance
    .setExpirationTime(now + 600) // 10 minute max
    .sign(privateKey)
}

/**
 * Exchange a GitHub App JWT for an installation access token.
 */
export async function getInstallationToken(
  installationId: string | number,
  appJwt: string,
): Promise<string> {
  const response = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${appJwt}`,
        'X-GitHub-Api-Version': '2022-11-28',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`GitHub API error: ${response.status} ${response.statusText}`)
  }

  const data = (await response.json()) as { token: string }
  return data.token
}

/**
 * List GitHub App installations using a short-lived app JWT.
 */
export async function listInstallations(
  appId: string,
  privateKeyPem: string,
): Promise<GitHubInstallation[]> {
  const appJwt = await createGitHubAppJwt(appId, privateKeyPem)
  const response = await fetch('https://api.github.com/app/installations', {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${appJwt}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  })

  if (!response.ok) {
    throw new Error(`GitHub API error: ${response.status} ${response.statusText}`)
  }

  const data = (await response.json()) as Array<{
    id: number
    app_slug?: string
    account?: { login?: string; type?: string }
  }>

  return data.map((installation) => ({
    id: installation.id,
    account: installation.account?.login || '',
    account_type: installation.account?.type || '',
    app_slug: installation.app_slug || '',
  }))
}

/**
 * List repositories visible to a GitHub App installation.
 */
export async function listInstallationRepos(
  installationId: string | number,
  appId: string,
  privateKeyPem: string,
): Promise<GitHubRepo[]> {
  const appJwt = await createGitHubAppJwt(appId, privateKeyPem)
  const token = await getInstallationToken(installationId, appJwt)
  const response = await fetch('https://api.github.com/installation/repositories', {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  })

  if (!response.ok) {
    throw new Error(`GitHub API error: ${response.status} ${response.statusText}`)
  }

  const data = (await response.json()) as {
    repositories?: Array<{
      id: number
      full_name: string
      private: boolean
      clone_url: string
      ssh_url?: string
    }>
  }

  return (data.repositories || []).map((repo) => ({
    id: repo.id,
    full_name: repo.full_name,
    private: repo.private,
    clone_url: repo.clone_url,
    ssh_url: repo.ssh_url,
  }))
}

/**
 * Provision git credentials for a GitHub App installation.
 */
export async function getGitCredentialsForInstallation(
  installationId: string | number,
  appId: string,
  privateKeyPem: string,
): Promise<GitHubCredentials> {
  const appJwt = await createGitHubAppJwt(appId, privateKeyPem)
  const token = await getInstallationToken(installationId, appJwt)
  return buildGitCredentials(token)
}

/**
 * Build git credentials for push/pull using an installation token.
 */
export function buildGitCredentials(installationToken: string): GitHubCredentials {
  return {
    username: 'x-access-token',
    password: installationToken,
  }
}

/**
 * Build the GitHub OAuth authorization URL.
 */
export function buildOAuthUrl(
  clientId: string,
  redirectUri: string,
  state: string,
): string {
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
    scope: 'read:user',
  })
  return `https://github.com/login/oauth/authorize?${params.toString()}`
}

/**
 * Exchange an OAuth code for an access token.
 */
export async function exchangeOAuthCode(
  clientId: string,
  clientSecret: string,
  code: string,
): Promise<{ access_token: string; token_type: string }> {
  const response = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      code,
    }),
  })

  if (!response.ok) {
    throw new Error(`GitHub OAuth error: ${response.status}`)
  }

  return (await response.json()) as { access_token: string; token_type: string }
}

/**
 * List GitHub App installations visible to an OAuth-authenticated user.
 */
export async function listUserInstallations(
  accessToken: string,
): Promise<GitHubInstallation[]> {
  const response = await fetch('https://api.github.com/user/installations', {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${accessToken}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  })

  if (!response.ok) {
    throw new Error(`GitHub API error: ${response.status} ${response.statusText}`)
  }

  const data = (await response.json()) as {
    installations?: Array<{
      id: number
      app_slug?: string
      account?: { login?: string; type?: string }
    }>
  }

  return (data.installations || []).map((installation) => ({
    id: installation.id,
    account: installation.account?.login || '',
    account_type: installation.account?.type || '',
    app_slug: installation.app_slug || '',
  }))
}

/**
 * Check if GitHub App integration is configured.
 */
export function isGitHubConfigured(config: ServerConfig): boolean {
  return !!(
    config.githubSyncEnabled &&
    config.githubAppId &&
    config.githubAppPrivateKey
  )
}
