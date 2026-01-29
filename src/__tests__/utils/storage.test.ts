/**
 * Tests for storage utility module
 *
 * Features tested:
 * - getItem/setItem with configured prefix
 * - Storage key generation
 * - Migration from legacy keys
 * - JSON serialization
 * - Prefix configuration
 * - Error handling
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  configureStorage,
  getStorageKey,
  getLegacyKey,
  getItem,
  setItem,
  removeItem,
  getJSON,
  setJSON,
  migrateLegacyKey,
  migrateAllLegacyKeys,
  createStorage,
  getPrefix,
  resetMigrationState,
  STORAGE_KEYS,
  LEGACY_PREFIX,
} from '../../utils/storage'

describe('Storage Utility', () => {
  beforeEach(() => {
    localStorage.clear()
    resetMigrationState()
    configureStorage({ prefix: 'test-app' })
  })

  afterEach(() => {
    localStorage.clear()
    resetMigrationState()
  })

  describe('Storage Key Generation', () => {
    it('generates storage key with configured prefix', () => {
      configureStorage({ prefix: 'myapp' })
      const key = getStorageKey('layout')
      expect(key).toBe('myapp-layout')
    })

    it('generates storage key with custom prefix override', () => {
      const key = getStorageKey('layout', 'custom')
      expect(key).toBe('custom-layout')
    })

    it('uses default prefix if not configured', () => {
      resetMigrationState()
      configureStorage({})
      const key = getStorageKey('layout')
      expect(key).toContain('layout')
    })

    it('generates legacy storage keys', () => {
      const key = getLegacyKey('layout')
      expect(key).toBe(`${LEGACY_PREFIX}-layout`)
    })

    it('returns correct prefix', () => {
      configureStorage({ prefix: 'myapp' })
      expect(getPrefix()).toBe('myapp')
    })
  })

  describe('getItem and setItem', () => {
    it('stores and retrieves string values', () => {
      setItem('layout', 'vertical')
      const value = getItem('layout')
      expect(value).toBe('vertical')
    })

    it('respects configured prefix', () => {
      configureStorage({ prefix: 'app1' })
      setItem('layout', 'value1')

      configureStorage({ prefix: 'app2' })
      setItem('layout', 'value2')

      // Each app has its own storage
      expect(getItem('layout')).toBe('value2')

      configureStorage({ prefix: 'app1' })
      expect(getItem('layout')).toBe('value1')
    })

    it('returns null for non-existent keys', () => {
      const value = getItem('nonexistent')
      expect(value).toBeNull()
    })

    it('overwrites existing values', () => {
      setItem('key', 'value1')
      expect(getItem('key')).toBe('value1')

      setItem('key', 'value2')
      expect(getItem('key')).toBe('value2')
    })

    it('handles errors gracefully', () => {
      // Mock localStorage to throw error
      const originalSetItem = Storage.prototype.setItem
      Storage.prototype.setItem = () => {
        throw new Error('Storage quota exceeded')
      }

      const result = setItem('key', 'value')
      expect(result).toBe(false)

      Storage.prototype.setItem = originalSetItem
    })
  })

  describe('removeItem', () => {
    it('removes stored items', () => {
      setItem('key', 'value')
      expect(getItem('key')).toBe('value')

      removeItem('key')
      expect(getItem('key')).toBeNull()
    })

    it('respects prefix when removing', () => {
      configureStorage({ prefix: 'app1' })
      setItem('key', 'value')

      removeItem('key')
      expect(getItem('key')).toBeNull()
    })

    it('returns false when removal fails', () => {
      const originalRemoveItem = Storage.prototype.removeItem
      Storage.prototype.removeItem = () => {
        throw new Error('Storage error')
      }

      const result = removeItem('key')
      expect(result).toBe(false)

      Storage.prototype.removeItem = originalRemoveItem
    })
  })

  describe('JSON Serialization', () => {
    it('stores and retrieves JSON objects', () => {
      const data = { color: 'dark', fontSize: 14 }
      setJSON('settings', data)

      const retrieved = getJSON('settings')
      expect(retrieved).toEqual(data)
    })

    it('returns default value for missing keys', () => {
      const defaultValue = { default: true }
      const result = getJSON('nonexistent', defaultValue)
      expect(result).toEqual(defaultValue)
    })

    it('returns default value on parse error', () => {
      // Store invalid JSON
      localStorage.setItem(getStorageKey('key'), '{invalid json}')

      const defaultValue = { fallback: true }
      const result = getJSON('key', defaultValue)
      expect(result).toEqual(defaultValue)
    })

    it('handles null default value', () => {
      const result = getJSON('nonexistent', null)
      expect(result).toBeNull()
    })

    it('handles arrays as JSON', () => {
      const items = ['a', 'b', 'c']
      setJSON('items', items)

      const retrieved = getJSON('items')
      expect(retrieved).toEqual(items)
    })
  })

  describe('Storage Constants', () => {
    it('exports known STORAGE_KEYS', () => {
      expect(STORAGE_KEYS).toHaveProperty('THEME')
      expect(STORAGE_KEYS).toHaveProperty('LAYOUT')
      expect(STORAGE_KEYS).toHaveProperty('TABS')
      expect(STORAGE_KEYS).toHaveProperty('PANEL_SIZES')
    })

    it('exports LEGACY_PREFIX', () => {
      expect(LEGACY_PREFIX).toBe('kurt-web')
    })
  })

  describe('Legacy Key Migration', () => {
    it('migrates single legacy key to new prefix', () => {
      // Set up legacy key
      localStorage.setItem(getLegacyKey('layout'), 'old-value')
      expect(localStorage.getItem(getLegacyKey('layout'))).toBe('old-value')

      // Migrate
      configureStorage({ prefix: 'newapp' })
      migrateLegacyKey('layout')

      // New key should have value
      expect(getItem('layout')).toBe('old-value')
      // Legacy key should be removed
      expect(localStorage.getItem(getLegacyKey('layout'))).toBeNull()
    })

    it('does not migrate if new key already exists', () => {
      // Set up both legacy and new keys
      localStorage.setItem(getLegacyKey('layout'), 'legacy-value')
      configureStorage({ prefix: 'newapp' })
      setItem('layout', 'new-value')

      // Attempt migration
      migrateLegacyKey('layout')

      // New value should be preserved
      expect(getItem('layout')).toBe('new-value')
    })

    it('returns false if legacy key does not exist', () => {
      configureStorage({ prefix: 'newapp' })
      const result = migrateLegacyKey('nonexistent')
      expect(result).toBe(false)
    })

    it('does not migrate if using legacy prefix', () => {
      localStorage.setItem(getLegacyKey('layout'), 'value')
      configureStorage({ prefix: LEGACY_PREFIX })

      const result = migrateLegacyKey('layout')
      expect(result).toBe(false)
    })

    it('migrates all legacy keys', () => {
      // Set up multiple legacy keys
      localStorage.setItem(getLegacyKey('layout'), 'layout-value')
      localStorage.setItem(getLegacyKey('theme'), 'dark')
      localStorage.setItem(getLegacyKey('tabs'), 'tab-data')

      configureStorage({ prefix: 'newapp' })
      resetMigrationState()

      const migrated = migrateAllLegacyKeys()

      expect(migrated.length).toBeGreaterThan(0)
      expect(getItem('layout')).toBe('layout-value')
      expect(getItem('theme')).toBe('dark')
      expect(getItem('tabs')).toBe('tab-data')
    })

    it('marks migration as completed', () => {
      const result1 = migrateAllLegacyKeys()
      const result2 = migrateAllLegacyKeys()

      // Second call should return empty array
      expect(result2).toEqual([])
    })
  })

  describe('createStorage Factory', () => {
    it('creates prefixed storage helper', () => {
      const storage = createStorage('project-123')

      storage.setItem('data', 'value')
      expect(storage.getItem('data')).toBe('value')
    })

    it('storage helper respects its own prefix', () => {
      const storage1 = createStorage('project-1')
      const storage2 = createStorage('project-2')

      storage1.setItem('key', 'value1')
      storage2.setItem('key', 'value2')

      expect(storage1.getItem('key')).toBe('value1')
      expect(storage2.getItem('key')).toBe('value2')
    })

    it('storage helper supports JSON operations', () => {
      const storage = createStorage('app')
      const data = { name: 'test', count: 42 }

      storage.setJSON('config', data)
      expect(storage.getJSON('config')).toEqual(data)
    })

    it('storage helper removes items', () => {
      const storage = createStorage('app')

      storage.setItem('key', 'value')
      expect(storage.getItem('key')).toBe('value')

      storage.removeItem('key')
      expect(storage.getItem('key')).toBeNull()
    })

    it('provides getStorageKey method', () => {
      const storage = createStorage('myapp')
      const key = storage.getStorageKey('layout')
      expect(key).toBe('myapp-layout')
    })
  })

  describe('Storage Prefixing with STORAGE_KEYS', () => {
    it('works with STORAGE_KEYS constants', () => {
      setItem(STORAGE_KEYS.THEME, 'dark')
      expect(getItem(STORAGE_KEYS.THEME)).toBe('dark')

      setItem(STORAGE_KEYS.LAYOUT, 'vertical')
      expect(getItem(STORAGE_KEYS.LAYOUT)).toBe('vertical')
    })

    it('prefixes STORAGE_KEYS correctly', () => {
      configureStorage({ prefix: 'myapp' })
      setItem(STORAGE_KEYS.THEME, 'dark')

      const actualKey = getStorageKey(STORAGE_KEYS.THEME)
      const storedValue = localStorage.getItem(actualKey)
      expect(storedValue).toBe('dark')
      expect(actualKey).toBe('myapp-theme')
    })
  })
})
