/**
 * Panel configuration and layout persistence helpers.
 *
 * Pure functions for panel sizing, layout state, and LRU caching.
 * Extracted from App.jsx for testability.
 *
 * @module utils/panelConfig
 */

import { getSharedStorageKey, loadCollapsedState, loadPanelSizes } from '../../layout'

export const arePlainObjectsEqual = (left, right) => {
  const leftEntries = Object.entries(left || {})
  const rightEntries = Object.entries(right || {})
  if (leftEntries.length !== rightEntries.length) return false
  return leftEntries.every(([key, value]) => right?.[key] === value)
}

export const panelIdToConfigKey = (panelId) =>
  String(panelId || '').replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase())

export const getPanelSizeConfigValue = (sizeConfig, panelId, fallbackKey) => {
  if (!sizeConfig || !panelId) return undefined
  const direct = sizeConfig[panelId]
  if (Number.isFinite(direct)) return direct
  const camelKey = panelIdToConfigKey(panelId)
  const camel = sizeConfig[camelKey]
  if (Number.isFinite(camel)) return camel
  const fallback = sizeConfig[fallbackKey]
  return Number.isFinite(fallback) ? fallback : undefined
}

const MAX_SCOPED_CACHE_ENTRIES = 12

export const getCachedScopedValue = (cache, key, createValue, onEvict) => {
  if (cache.has(key)) {
    const existing = cache.get(key)
    cache.delete(key)
    cache.set(key, existing)
    return existing
  }

  const created = createValue()
  cache.set(key, created)
  if (cache.size > MAX_SCOPED_CACHE_ENTRIES) {
    const oldestKey = cache.keys().next().value
    const oldestValue = cache.get(oldestKey)
    cache.delete(oldestKey)
    if (onEvict) onEvict(oldestValue, oldestKey)
  }
  return created
}

export const isStableLightningUserScope = (scope) => (
  scope.startsWith('u-')
  || scope.startsWith('e-')
  || scope.startsWith('anon-')
  || scope.startsWith('auth-')
)

const hasSharedPreferenceValue = (prefix, suffix) => {
  if (!prefix) return false
  try {
    return localStorage.getItem(getSharedStorageKey(prefix, suffix)) !== null
  } catch {
    return false
  }
}

const resolveSharedPreferencePrefix = (prefix, fallbackPrefix, suffix) => {
  if (hasSharedPreferenceValue(prefix, suffix)) return prefix
  if (prefix !== fallbackPrefix && hasSharedPreferenceValue(fallbackPrefix, suffix)) {
    return fallbackPrefix
  }
  return prefix
}

export const readPersistedCollapsedState = (prefix, fallbackPrefix) => {
  const effectivePrefix = resolveSharedPreferencePrefix(prefix, fallbackPrefix, 'sidebar-collapsed')
  const saved = loadCollapsedState(effectivePrefix)
  return { filetree: false, terminal: false, shell: false, agent: false, ...saved }
}

export const readPersistedPanelSizes = (prefix, fallbackPrefix, panelDefaults, agentSize) => {
  const effectivePrefix = resolveSharedPreferencePrefix(prefix, fallbackPrefix, 'panel-sizes')
  return {
    ...panelDefaults,
    agent: agentSize,
    ...(loadPanelSizes(effectivePrefix) || {}),
  }
}
