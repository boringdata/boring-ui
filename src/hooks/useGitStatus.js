import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi } from './useApi';
import { useConfig } from '../config';

/**
 * Git file status codes
 * @typedef {'M' | 'A' | 'D' | 'U' | '?' | 'R' | 'C'} GitStatusCode
 */

/**
 * Git status for a file
 * @typedef {Object} GitFileStatus
 * @property {string} path - The file path
 * @property {GitStatusCode} status - The status code
 * @property {string} [oldPath] - Original path for renamed files
 */

/**
 * Git status response
 * @typedef {Object} GitStatusResponse
 * @property {boolean} available - Whether git is available
 * @property {string} [branch] - Current branch name
 * @property {Object<string, GitStatusCode>} [files] - Map of file paths to status codes
 * @property {boolean} [clean] - Whether the working directory is clean
 */

/**
 * Git status hook return value
 * @typedef {Object} UseGitStatusReturn
 * @property {GitStatusResponse | null} status - The git status data
 * @property {boolean} loading - Whether the status is loading
 * @property {Error | null} error - Error if fetch failed
 * @property {function(): Promise<void>} refetch - Manual refetch function
 */

/**
 * Hook options
 * @typedef {Object} UseGitStatusOptions
 * @property {string} [path] - Specific file path to get status for
 * @property {boolean} [polling=true] - Whether to enable polling
 * @property {number} [pollInterval] - Override poll interval (uses config.fileTree.gitPollInterval by default)
 */

/**
 * Custom hook for fetching git status with automatic polling
 *
 * @param {UseGitStatusOptions} [options={}] - Hook options
 * @returns {UseGitStatusReturn} Git status state and controls
 *
 * @example
 * ```jsx
 * // Basic usage - get all git status with polling
 * const { status, loading, error, refetch } = useGitStatus();
 *
 * // Get status for a specific file
 * const { status } = useGitStatus({ path: 'src/App.jsx' });
 *
 * // Disable polling
 * const { status } = useGitStatus({ polling: false });
 *
 * // Custom poll interval
 * const { status } = useGitStatus({ pollInterval: 10000 });
 * ```
 */
export function useGitStatus(options = {}) {
  const { path, polling = true, pollInterval: customInterval } = options;

  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const api = useApi();
  const config = useConfig();

  // Get poll interval from config or use custom
  const pollInterval = customInterval ?? config.fileTree?.gitPollInterval ?? 5000;

  // Use ref to track mounted state
  const mountedRef = useRef(true);

  // Use ref for interval to allow cleanup
  const intervalRef = useRef(null);

  /**
   * Fetch git status from API
   */
  const fetchStatus = useCallback(async () => {
    try {
      // Build endpoint URL
      let endpoint = '/api/git/status';
      if (path) {
        endpoint += `?path=${encodeURIComponent(path)}`;
      }

      const { data, error: fetchError } = await api.get(endpoint);

      // Only update state if still mounted
      if (!mountedRef.current) return;

      if (fetchError) {
        setError(fetchError);
        setLoading(false);
        return;
      }

      setStatus(data);
      setError(null);
      setLoading(false);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error(String(err)));
      setLoading(false);
    }
  }, [api, path]);

  /**
   * Manual refetch function
   */
  const refetch = useCallback(async () => {
    setLoading(true);
    await fetchStatus();
  }, [fetchStatus]);

  // Initial fetch and polling setup
  useEffect(() => {
    mountedRef.current = true;

    // Initial fetch
    fetchStatus();

    // Setup polling if enabled
    if (polling && pollInterval > 0) {
      intervalRef.current = setInterval(fetchStatus, pollInterval);
    }

    // Cleanup
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [fetchStatus, polling, pollInterval]);

  return {
    status,
    loading,
    error,
    refetch,
  };
}

/**
 * Get the status code for a specific file from the git status
 *
 * @param {GitStatusResponse | null} status - The git status response
 * @param {string} filePath - The file path to check
 * @returns {GitStatusCode | null} The status code or null if not found/modified
 */
export function getFileStatus(status, filePath) {
  if (!status?.files || !filePath) return null;

  // Normalize path (remove leading slash if present)
  const normalizedPath = filePath.startsWith('/') ? filePath.slice(1) : filePath;

  return status.files[normalizedPath] || status.files[filePath] || null;
}

/**
 * Status code configuration with labels and CSS classes
 */
export const STATUS_CONFIG = {
  M: { label: 'Modified', className: 'git-status-modified', color: '#e5c07b' },
  A: { label: 'Added', className: 'git-status-added', color: '#98c379' },
  D: { label: 'Deleted', className: 'git-status-deleted', color: '#e06c75' },
  U: { label: 'Untracked', className: 'git-status-untracked', color: '#61afef' },
  '?': { label: 'Untracked', className: 'git-status-untracked', color: '#61afef' },
  R: { label: 'Renamed', className: 'git-status-renamed', color: '#c678dd' },
  C: { label: 'Copied', className: 'git-status-copied', color: '#56b6c2' },
};

/**
 * Get configuration for a status code
 *
 * @param {GitStatusCode | null} statusCode - The status code
 * @returns {{ label: string, className: string, color: string } | null} Status config or null
 */
export function getStatusConfig(statusCode) {
  if (!statusCode) return null;
  return STATUS_CONFIG[statusCode] || null;
}

export default useGitStatus;
