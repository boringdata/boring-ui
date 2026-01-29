/**
 * Storage utility for localStorage with configurable prefix
 *
 * Provides helper functions for localStorage operations with automatic key prefixing
 * based on app configuration. Also supports migration from legacy storage keys.
 */

// Default prefix when not using config context (module-level fallback)
let modulePrefix = 'kurt-web';
let legacyMigrationMap = null;
let migrationCompleted = false;

/**
 * Legacy prefix used by older versions of the app
 * @constant {string}
 */
export const LEGACY_PREFIX = 'kurt-web';

/**
 * Known storage key suffixes used throughout the app
 * @constant {Object}
 */
export const STORAGE_KEYS = {
  LAYOUT: 'layout',
  TABS: 'tabs',
  SIDEBAR_COLLAPSED: 'sidebar-collapsed',
  PANEL_SIZES: 'panel-sizes',
  TERMINAL_SESSIONS: 'terminal-sessions',
  TERMINAL_ACTIVE: 'terminal-active',
  TERMINAL_VIEW_MODE: 'terminal-view-mode',
  TERMINAL_CHAT_INTERFACE: 'terminal-chat-interface',
  SHELL_SESSIONS: 'shell-sessions',
  SHELL_ACTIVE: 'shell-active',
  CLAUDE_STREAM_HISTORY: 'claude-stream-history',
  CLI_OPTIONS: 'claude-cli-options',
  PTY_HISTORY: 'pty-history',
  THEME: 'theme',
};

/**
 * Configure the storage module with app settings
 * Should be called once during app initialization
 *
 * @param {Object} options - Configuration options
 * @param {string} [options.prefix='kurt-web'] - Storage key prefix
 * @param {Object} [options.migrateLegacyKeys] - Map of old key suffixes to new key suffixes
 */
export function configureStorage(options = {}) {
  if (options.prefix) {
    modulePrefix = options.prefix;
  }
  if (options.migrateLegacyKeys) {
    legacyMigrationMap = options.migrateLegacyKeys;
  }
}

/**
 * Get the full storage key with the configured prefix
 *
 * @param {string} key - The key suffix (e.g., 'layout', 'tabs')
 * @param {string} [prefix] - Optional prefix override
 * @returns {string} The full storage key (e.g., 'myapp-layout')
 *
 * @example
 * getStorageKey('layout') // returns 'myapp-layout' (with 'myapp' prefix)
 * getStorageKey('layout', 'custom') // returns 'custom-layout'
 */
export function getStorageKey(key, prefix) {
  const p = prefix ?? modulePrefix;
  return `${p}-${key}`;
}

/**
 * Get the legacy storage key (with 'kurt-web-' prefix)
 *
 * @param {string} key - The key suffix
 * @returns {string} The legacy key (e.g., 'kurt-web-layout')
 */
export function getLegacyKey(key) {
  return `${LEGACY_PREFIX}-${key}`;
}

/**
 * Migrate a single legacy key to the new prefixed key
 * Only migrates if the legacy key exists and the new key doesn't
 *
 * @param {string} keySuffix - The key suffix to migrate
 * @param {string} [prefix] - Optional prefix override
 * @returns {boolean} True if migration occurred
 */
export function migrateLegacyKey(keySuffix, prefix) {
  const legacyKey = getLegacyKey(keySuffix);
  const newKey = getStorageKey(keySuffix, prefix);

  // Don't migrate if same key (prefix is 'kurt-web')
  if (legacyKey === newKey) return false;

  try {
    const legacyValue = localStorage.getItem(legacyKey);
    if (legacyValue !== null) {
      const newValue = localStorage.getItem(newKey);
      // Only migrate if new key doesn't exist
      if (newValue === null) {
        localStorage.setItem(newKey, legacyValue);
        // Remove legacy key after successful migration
        localStorage.removeItem(legacyKey);
        return true;
      }
    }
  } catch {
    // Ignore storage errors
  }
  return false;
}

/**
 * Migrate all known legacy keys to the new prefix
 * Should be called once during app initialization
 *
 * @param {string} [prefix] - Optional prefix override
 * @returns {string[]} List of migrated key suffixes
 */
export function migrateAllLegacyKeys(prefix) {
  if (migrationCompleted) return [];

  const migrated = [];
  const keysToMigrate = Object.values(STORAGE_KEYS);

  for (const keySuffix of keysToMigrate) {
    if (migrateLegacyKey(keySuffix, prefix)) {
      migrated.push(keySuffix);
    }
  }

  // Also migrate any project-specific keys (with hash suffix)
  try {
    const keysInStorage = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(`${LEGACY_PREFIX}-`)) {
        keysInStorage.push(key);
      }
    }

    for (const fullLegacyKey of keysInStorage) {
      const suffix = fullLegacyKey.slice(LEGACY_PREFIX.length + 1);
      const newKey = getStorageKey(suffix, prefix);

      // Don't migrate if same key or new key exists
      if (fullLegacyKey === newKey) continue;

      try {
        const newValue = localStorage.getItem(newKey);
        if (newValue === null) {
          const legacyValue = localStorage.getItem(fullLegacyKey);
          if (legacyValue !== null) {
            localStorage.setItem(newKey, legacyValue);
            localStorage.removeItem(fullLegacyKey);
            migrated.push(suffix);
          }
        }
      } catch {
        // Ignore individual key errors
      }
    }
  } catch {
    // Ignore storage enumeration errors
  }

  // Handle custom migration map if configured
  if (legacyMigrationMap) {
    for (const [oldSuffix, newSuffix] of Object.entries(legacyMigrationMap)) {
      const oldKey = getLegacyKey(oldSuffix);
      const newKey = getStorageKey(newSuffix, prefix);

      try {
        const oldValue = localStorage.getItem(oldKey);
        if (oldValue !== null) {
          const existingValue = localStorage.getItem(newKey);
          if (existingValue === null) {
            localStorage.setItem(newKey, oldValue);
            localStorage.removeItem(oldKey);
            migrated.push(`${oldSuffix} -> ${newSuffix}`);
          }
        }
      } catch {
        // Ignore individual key errors
      }
    }
  }

  migrationCompleted = true;
  return migrated;
}

/**
 * Get an item from localStorage with the configured prefix
 *
 * @param {string} key - The key suffix
 * @param {string} [prefix] - Optional prefix override
 * @returns {string|null} The stored value or null
 *
 * @example
 * const layout = getItem('layout')
 * const projectLayout = getItem(`${projectHash}-layout`)
 */
export function getItem(key, prefix) {
  try {
    return localStorage.getItem(getStorageKey(key, prefix));
  } catch {
    return null;
  }
}

/**
 * Set an item in localStorage with the configured prefix
 *
 * @param {string} key - The key suffix
 * @param {string} value - The value to store
 * @param {string} [prefix] - Optional prefix override
 * @returns {boolean} True if successful
 *
 * @example
 * setItem('layout', JSON.stringify(layoutData))
 */
export function setItem(key, value, prefix) {
  try {
    localStorage.setItem(getStorageKey(key, prefix), value);
    return true;
  } catch {
    return false;
  }
}

/**
 * Remove an item from localStorage with the configured prefix
 *
 * @param {string} key - The key suffix
 * @param {string} [prefix] - Optional prefix override
 * @returns {boolean} True if successful
 *
 * @example
 * removeItem('layout')
 */
export function removeItem(key, prefix) {
  try {
    localStorage.removeItem(getStorageKey(key, prefix));
    return true;
  } catch {
    return false;
  }
}

/**
 * Get a JSON-parsed item from localStorage
 *
 * @param {string} key - The key suffix
 * @param {*} [defaultValue=null] - Default value if key doesn't exist or parse fails
 * @param {string} [prefix] - Optional prefix override
 * @returns {*} The parsed value or default
 *
 * @example
 * const collapsed = getJSON('sidebar-collapsed', { filetree: false })
 */
export function getJSON(key, defaultValue = null, prefix) {
  try {
    const value = getItem(key, prefix);
    if (value === null) return defaultValue;
    return JSON.parse(value);
  } catch {
    return defaultValue;
  }
}

/**
 * Set a JSON-stringified item in localStorage
 *
 * @param {string} key - The key suffix
 * @param {*} value - The value to stringify and store
 * @param {string} [prefix] - Optional prefix override
 * @returns {boolean} True if successful
 *
 * @example
 * setJSON('panel-sizes', { filetree: 280, terminal: 400 })
 */
export function setJSON(key, value, prefix) {
  try {
    return setItem(key, JSON.stringify(value), prefix);
  } catch {
    return false;
  }
}

/**
 * Create a storage helper bound to a specific prefix
 * Useful for creating project-specific storage instances
 *
 * @param {string} prefix - The prefix to use
 * @returns {Object} Storage helper object with getItem, setItem, removeItem, getJSON, setJSON
 *
 * @example
 * const projectStorage = createStorage('myapp-abc123')
 * projectStorage.setJSON('layout', layoutData)
 */
export function createStorage(prefix) {
  return {
    prefix,
    getStorageKey: (key) => getStorageKey(key, prefix),
    getItem: (key) => getItem(key, prefix),
    setItem: (key, value) => setItem(key, value, prefix),
    removeItem: (key) => removeItem(key, prefix),
    getJSON: (key, defaultValue) => getJSON(key, defaultValue, prefix),
    setJSON: (key, value) => setJSON(key, value, prefix),
  };
}

/**
 * Get the current configured prefix
 *
 * @returns {string} The current prefix
 */
export function getPrefix() {
  return modulePrefix;
}

/**
 * Check if migration has been completed
 *
 * @returns {boolean} True if migration has run
 */
export function isMigrationCompleted() {
  return migrationCompleted;
}

/**
 * Reset migration state (for testing)
 */
export function resetMigrationState() {
  migrationCompleted = false;
}

export default {
  LEGACY_PREFIX,
  STORAGE_KEYS,
  configureStorage,
  getStorageKey,
  getLegacyKey,
  migrateLegacyKey,
  migrateAllLegacyKeys,
  getItem,
  setItem,
  removeItem,
  getJSON,
  setJSON,
  createStorage,
  getPrefix,
  isMigrationCompleted,
  resetMigrationState,
};
