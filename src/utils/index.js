/**
 * Utility module exports
 */

export {
  // Constants
  LEGACY_PREFIX,
  STORAGE_KEYS,
  // Configuration
  configureStorage,
  // Key generation
  getStorageKey,
  getLegacyKey,
  // Migration
  migrateLegacyKey,
  migrateAllLegacyKeys,
  isMigrationCompleted,
  resetMigrationState,
  // Storage operations
  getItem,
  setItem,
  removeItem,
  getJSON,
  setJSON,
  // Factory
  createStorage,
  getPrefix,
} from './storage';
