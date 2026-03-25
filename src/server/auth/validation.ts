/**
 * Auth validation — redirect URL allowlisting, config checks.
 * Prevents open redirect attacks in OAuth/auth callback flows.
 */

const SAFE_REDIRECT_RE = /^\/[^/\\]/

/**
 * Validate that a redirect URL is safe (relative path only).
 * Prevents open redirect attacks by rejecting:
 * - Absolute URLs (https://evil.com)
 * - Protocol-relative URLs (//evil.com)
 * - Backslash paths (\\evil.com)
 * - Empty strings
 *
 * @returns The validated redirect URL, or the fallback
 */
export function validateRedirectUrl(
  url: string | undefined | null,
  fallback: string = '/',
): string {
  if (!url?.trim()) return fallback
  const trimmed = url.trim()

  // Only allow relative paths starting with /
  if (!SAFE_REDIRECT_RE.test(trimmed)) return fallback

  return trimmed
}

/**
 * Validate startup auth configuration.
 * Called during server startup — throws on misconfiguration.
 */
export function validateAuthConfig(config: {
  controlPlaneProvider: string
  neonAuthBaseUrl?: string
  sessionSecret?: string
}): void {
  if (config.controlPlaneProvider === 'neon') {
    if (!config.neonAuthBaseUrl) {
      throw new Error(
        'NEON_AUTH_BASE_URL is required when CONTROL_PLANE_PROVIDER=neon',
      )
    }
  }

  if (!config.sessionSecret) {
    throw new Error(
      'Session secret is required. Set BORING_UI_SESSION_SECRET or BORING_SESSION_SECRET.',
    )
  }
}
