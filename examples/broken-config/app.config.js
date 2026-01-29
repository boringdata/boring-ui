/**
 * INTENTIONALLY BROKEN configuration for testing config validation
 *
 * This file demonstrates what happens when you have invalid configuration.
 * Run the app with this config to see the error UI.
 *
 * To test:
 * 1. Copy this file to your project's app.config.js
 * 2. Start the dev server
 * 3. You should see a "Configuration Error" page with all validation errors listed
 */

export default {
  // Invalid branding - name should be a string
  branding: {
    name: 12345,  // ERROR: Expected string, got number
    logo: null,   // This is actually valid (string or component)
  },

  // Invalid fileTree config
  fileTree: {
    // ERROR: sections items missing required fields
    sections: [
      { key: 'dashboards' },  // Missing 'label' and 'icon'
      { key: 123, label: 'Models', icon: 'Database' },  // 'key' should be string
    ],
    // ERROR: gitPollInterval should be positive integer
    gitPollInterval: -5000,
    // ERROR: treePollInterval should be a number, not string
    treePollInterval: 'three seconds',
  },

  // Invalid storage config
  storage: {
    prefix: 'test',
    layoutVersion: -1,  // ERROR: Should be non-negative
  },

  // Invalid features - should be booleans
  features: {
    gitStatus: 'yes',     // ERROR: Expected boolean
    search: 1,            // ERROR: Expected boolean
    cloudMode: undefined, // This might be OK (will use default)
    workflows: 'false',   // ERROR: Expected boolean, got string
  },
}
