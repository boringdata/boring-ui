import { createContext, useContext, useEffect, useState } from 'react';
import { safeParseAppConfig, appConfigSchema } from './schema';

/**
 * Context for application configuration
 * @type {React.Context<import('./types').AppConfig | null>}
 */
const ConfigContext = createContext(null);

/**
 * Get a nested value from an object using a dot-notation path
 * @param {object} obj - The object to get the value from
 * @param {string} path - Dot-notation path (e.g., 'branding.name')
 * @returns {*} The value at the path, or undefined if not found
 */
function getNestedValue(obj, path) {
  if (!obj || typeof path !== 'string') return undefined;

  const keys = path.split('.');
  let current = obj;

  for (const key of keys) {
    if (current === null || current === undefined) {
      return undefined;
    }
    current = current[key];
  }

  return current;
}

/**
 * Get default configuration with all defaults applied
 * @returns {import('./types').AppConfig}
 */
function getDefaultConfig() {
  return appConfigSchema.parse({});
}

/**
 * Format Zod validation errors into a human-readable list
 * @param {import('zod').ZodError} zodError - The Zod error object
 * @returns {string[]} Array of formatted error messages
 */
function formatValidationErrors(zodError) {
  const errors = [];

  for (const issue of zodError.issues) {
    const path = issue.path.length > 0 ? issue.path.join('.') : '(root)';
    const message = issue.message;
    const code = issue.code;

    // Include expected/received for type errors
    let details = '';
    if (code === 'invalid_type') {
      details = ` (expected ${issue.expected}, received ${issue.received})`;
    } else if (code === 'invalid_enum_value') {
      details = ` (valid options: ${issue.options?.join(', ')})`;
    }

    errors.push(`  - ${path}: ${message}${details}`);
  }

  return errors;
}

/**
 * Configuration error component - displays when config validation fails
 */
function ConfigError({ errors }) {
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: '#1a1a2e',
      color: '#e0e0e0',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      padding: '2rem',
      overflow: 'auto',
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '0 auto',
      }}>
        <div style={{
          backgroundColor: '#2d1f3d',
          border: '1px solid #ff6b6b',
          borderRadius: '8px',
          padding: '1.5rem',
          marginBottom: '1.5rem',
        }}>
          <h1 style={{
            color: '#ff6b6b',
            fontSize: '1.5rem',
            fontWeight: 600,
            margin: '0 0 0.5rem 0',
          }}>
            Configuration Error
          </h1>
          <p style={{
            color: '#b0b0b0',
            margin: 0,
            fontSize: '0.9rem',
          }}>
            The application configuration is invalid. Please fix the following errors in your app.config.js file.
          </p>
        </div>

        <div style={{
          backgroundColor: '#16213e',
          border: '1px solid #3d3d5c',
          borderRadius: '8px',
          padding: '1.5rem',
        }}>
          <h2 style={{
            color: '#ffd93d',
            fontSize: '1rem',
            fontWeight: 600,
            margin: '0 0 1rem 0',
          }}>
            Validation Errors ({errors.length})
          </h2>
          <pre style={{
            margin: 0,
            fontFamily: 'ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace',
            fontSize: '0.85rem',
            lineHeight: 1.6,
            color: '#e0e0e0',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
{errors.join('\n')}
          </pre>
        </div>

        <div style={{
          marginTop: '1.5rem',
          padding: '1rem',
          backgroundColor: '#1e3a5f',
          borderRadius: '8px',
          border: '1px solid #4a6fa5',
        }}>
          <p style={{
            margin: 0,
            fontSize: '0.85rem',
            color: '#a0c4ff',
          }}>
            <strong>Tip:</strong> Check the browser console for the full error details.
            After fixing your configuration, refresh the page.
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * ConfigProvider component that provides validated configuration to the app
 *
 * Validates configuration on mount and fails fast with invalid config:
 * - Logs ALL validation errors to console (not just the first one)
 * - Shows a helpful error UI explaining what's wrong
 * - Prevents the app from rendering with invalid configuration
 *
 * @param {object} props
 * @param {object} [props.config] - Raw configuration object (will be validated and merged with defaults)
 * @param {boolean} [props.failFast=true] - If true, show error UI on validation failure. If false, fall back to defaults (legacy behavior)
 * @param {React.ReactNode} props.children - Child components
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * import { ConfigProvider } from './config'
 * import appConfig from './app.config'
 *
 * // In App.jsx
 * <ConfigProvider config={appConfig}>
 *   <App />
 * </ConfigProvider>
 * ```
 */
export function ConfigProvider({ config, failFast = true, children }) {
  const [validationState, setValidationState] = useState(() => {
    // If no config provided, use defaults (this is valid)
    if (!config) {
      return { valid: true, config: getDefaultConfig(), errors: null };
    }

    // Validate and parse the config with Zod
    const result = safeParseAppConfig(config);

    if (!result.success) {
      // Format all validation errors for display
      const formattedErrors = formatValidationErrors(result.error);

      // Log ALL errors to console with full details
      console.error(
        '[ConfigProvider] Configuration validation failed!\n\n' +
        'The following errors were found:\n' +
        formattedErrors.join('\n') +
        '\n\nFull error details:',
        result.error.format()
      );

      // Also log the raw config that was provided for debugging
      console.error('[ConfigProvider] Provided config:', config);

      if (failFast) {
        return { valid: false, config: null, errors: formattedErrors };
      }

      // Legacy behavior: fall back to defaults
      console.warn('[ConfigProvider] Falling back to default configuration due to validation errors');
      return { valid: true, config: getDefaultConfig(), errors: null };
    }

    return { valid: true, config: result.data, errors: null };
  });

  // Re-validate if config changes (rare, but possible in hot reload scenarios)
  useEffect(() => {
    // Skip initial validation (already done in useState initializer)
    // This effect only handles subsequent config changes
    const result = config ? safeParseAppConfig(config) : { success: true, data: getDefaultConfig() };

    if (!config) {
      setValidationState({ valid: true, config: getDefaultConfig(), errors: null });
      return;
    }

    if (!result.success) {
      const formattedErrors = formatValidationErrors(result.error);

      console.error(
        '[ConfigProvider] Configuration validation failed!\n\n' +
        'The following errors were found:\n' +
        formattedErrors.join('\n') +
        '\n\nFull error details:',
        result.error.format()
      );
      console.error('[ConfigProvider] Provided config:', config);

      if (failFast) {
        setValidationState({ valid: false, config: null, errors: formattedErrors });
        return;
      }

      console.warn('[ConfigProvider] Falling back to default configuration due to validation errors');
      setValidationState({ valid: true, config: getDefaultConfig(), errors: null });
      return;
    }

    setValidationState({ valid: true, config: result.data, errors: null });
  }, [config, failFast]);

  // If validation failed and failFast is enabled, show error UI
  if (!validationState.valid && validationState.errors) {
    return <ConfigError errors={validationState.errors} />;
  }

  return (
    <ConfigContext.Provider value={validationState.config}>
      {children}
    </ConfigContext.Provider>
  );
}

/**
 * Hook to access the full application configuration
 * Must be used within a ConfigProvider
 *
 * @returns {import('./types').AppConfig} The validated configuration object
 * @throws {Error} If used outside of ConfigProvider
 *
 * @example
 * ```jsx
 * import { useConfig } from './config'
 *
 * function MyComponent() {
 *   const { branding, features } = useConfig();
 *   return <h1>{branding.name}</h1>;
 * }
 * ```
 */
export function useConfig() {
  const config = useContext(ConfigContext);

  if (config === null) {
    throw new Error(
      'useConfig must be used within a ConfigProvider. ' +
      'Wrap your app in <ConfigProvider config={...}>.'
    );
  }

  return config;
}

/**
 * Hook to access a specific configuration value using dot-notation path
 * Useful for deeply nested config values without destructuring
 *
 * @param {string} path - Dot-notation path to the config value (e.g., 'branding.name')
 * @returns {*} The value at the specified path, or undefined if not found
 * @throws {Error} If used outside of ConfigProvider
 *
 * @example
 * ```jsx
 * import { useConfigValue } from './config'
 *
 * function MyComponent() {
 *   const appName = useConfigValue('branding.name');
 *   const gitPolling = useConfigValue('fileTree.gitPollInterval');
 *   const hasSearch = useConfigValue('features.search');
 *
 *   return <h1>{appName}</h1>;
 * }
 * ```
 */
export function useConfigValue(path) {
  const config = useConfig();
  return getNestedValue(config, path);
}

export default ConfigProvider;
