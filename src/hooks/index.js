/**
 * boring-ui Hooks
 *
 * Export barrel for all reusable React hooks.
 */

// Theme management hook with provider
export { useTheme, ThemeProvider, getInitialTheme, applyTheme, persistTheme, DEFAULT_STORAGE_KEY } from './useTheme.jsx';

// API hook for making requests with configurable baseUrl
export { useApi } from './useApi.js';

// Git status hook for polling git status from API
export {
  useGitStatus,
  getFileStatus,
  getStatusConfig,
  STATUS_CONFIG,
} from './useGitStatus.js';
