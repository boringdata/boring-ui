/**
 * Configuration module for boring-ui
 * Exports Zod schemas, TypeScript types, and React context for app.config.js
 */

export {
  // Individual schemas
  brandingSchema,
  fileTreeSectionSchema,
  fileTreeSchema,
  storageSchema,
  panelsSchema,
  apiSchema,
  featuresSchema,
  // Main config schema
  appConfigSchema,
  // Helper functions
  parseAppConfig,
  safeParseAppConfig,
} from './schema';

// React context provider and hooks
export {
  ConfigProvider,
  useConfig,
  useConfigValue,
} from './ConfigProvider';

// Storage utilities - re-export for convenience
export {
  configureStorage,
  migrateAllLegacyKeys,
  STORAGE_KEYS,
  LEGACY_PREFIX,
} from '../utils/storage';

// Re-export types (for TypeScript consumers)
// Types are available via the types.d.ts file
