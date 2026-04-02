/**
 * useChatCenteredShell — decides which layout to render.
 *
 * Reads the feature flag `features.chatCenteredShell` from app config.
 * Supports dev overrides via URL search params:
 *   ?layout=chat           — chat-centered layout (new)
 *   ?layout=ide            — IDE/Dockview layout (legacy)
 *   ?shell=chat-centered   — backward compat alias for layout=chat
 *   ?shell=legacy           — backward compat alias for layout=ide
 *
 * @returns {{ enabled: boolean, layout: 'chat'|'ide' }}
 */

import { useMemo } from 'react'
import { getConfig } from '../../shared/config/appConfig'

/**
 * @returns {{ enabled: boolean, layout: 'chat'|'ide' }}
 */
export function useChatCenteredShell() {
  return useMemo(() => {
    const params = new URLSearchParams(window.location.search)

    // New param: ?layout=chat|ide
    const layoutParam = params.get('layout')
    if (layoutParam === 'chat') return { enabled: true, layout: 'chat' }
    if (layoutParam === 'ide') return { enabled: false, layout: 'ide' }

    // Backward compat: ?shell=chat-centered|legacy
    const shellParam = params.get('shell')
    if (shellParam === 'chat-centered' || shellParam === 'chat') return { enabled: true, layout: 'chat' }
    if (shellParam === 'legacy' || shellParam === 'ide') return { enabled: false, layout: 'ide' }

    // Config fallback
    const config = getConfig()
    const enabled = config?.features?.chatCenteredShell === true
    return { enabled, layout: enabled ? 'chat' : 'ide' }
  }, [])
}
