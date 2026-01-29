import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useConfig } from '../config';

/**
 * API response structure returned by all fetch methods
 * @typedef {Object} ApiResponse
 * @property {*} data - The parsed response data (or null if error)
 * @property {boolean} loading - Whether the request is in progress
 * @property {Error|null} error - Error object if request failed
 * @property {Response|null} response - The raw fetch Response object
 */

/**
 * Request interceptor function type
 * @typedef {function(string, RequestInit): {url: string, options: RequestInit} | Promise<{url: string, options: RequestInit}>} RequestInterceptor
 */

/**
 * Response interceptor function type
 * @typedef {function(Response, *): * | Promise<*>} ResponseInterceptor
 */

/**
 * Options for useApi hook
 * @typedef {Object} UseApiOptions
 * @property {RequestInterceptor} [requestInterceptor] - Function to modify requests before they are sent
 * @property {ResponseInterceptor} [responseInterceptor] - Function to process responses before returning
 * @property {Object} [defaultHeaders] - Default headers to include in all requests
 */

/**
 * Custom hook for making API requests with configurable baseUrl from app config
 *
 * @param {UseApiOptions} [options={}] - Hook configuration options
 * @returns {Object} API methods object
 *
 * @example
 * ```jsx
 * import { useApi } from './hooks/useApi';
 *
 * function MyComponent() {
 *   const api = useApi();
 *
 *   const fetchData = async () => {
 *     const { data, loading, error } = await api.get('/sessions');
 *     if (error) {
 *       console.error('Failed to fetch:', error);
 *       return;
 *     }
 *     console.log('Sessions:', data);
 *   };
 *
 *   const createSession = async () => {
 *     const { data, error } = await api.post('/sessions', { name: 'new' });
 *     if (!error) {
 *       console.log('Created session:', data);
 *     }
 *   };
 *
 *   return <button onClick={fetchData}>Fetch</button>;
 * }
 * ```
 *
 * @example
 * // With interceptors
 * ```jsx
 * const api = useApi({
 *   requestInterceptor: ({ url, options }) => {
 *     // Add auth token to all requests
 *     return {
 *       url,
 *       options: {
 *         ...options,
 *         headers: {
 *           ...options.headers,
 *           'Authorization': `Bearer ${getToken()}`
 *         }
 *       }
 *     };
 *   },
 *   responseInterceptor: (response, data) => {
 *     // Transform response data
 *     return data.items || data;
 *   }
 * });
 * ```
 */
export function useApi(options = {}) {
  const config = useConfig();
  const baseUrl = config.api?.baseUrl || '';

  // Use refs to avoid recreating callbacks when interceptors change
  const requestInterceptorRef = useRef(options.requestInterceptor);
  const responseInterceptorRef = useRef(options.responseInterceptor);
  const defaultHeadersRef = useRef(options.defaultHeaders);

  // Update refs when options change (in effect to avoid lint warnings)
  useEffect(() => {
    requestInterceptorRef.current = options.requestInterceptor;
    responseInterceptorRef.current = options.responseInterceptor;
    defaultHeadersRef.current = options.defaultHeaders;
  }, [options.requestInterceptor, options.responseInterceptor, options.defaultHeaders]);

  /**
   * Build full URL from path
   * @param {string} path - API endpoint path
   * @returns {string} Full URL
   */
  const buildUrl = useCallback((path) => {
    // If path is already a full URL, return as-is
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path;
    }

    // Normalize path to ensure it starts with /
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;

    // Remove trailing slash from baseUrl if present
    const normalizedBase = baseUrl.endsWith('/')
      ? baseUrl.slice(0, -1)
      : baseUrl;

    return `${normalizedBase}${normalizedPath}`;
  }, [baseUrl]);

  /**
   * Core fetch function with error handling and interceptors
   * @param {string} path - API endpoint path
   * @param {RequestInit} [fetchOptions={}] - Fetch options
   * @returns {Promise<ApiResponse>} API response object
   */
  const request = useCallback(async (path, fetchOptions = {}) => {
    let url = buildUrl(path);

    // Merge default headers
    const headers = {
      'Content-Type': 'application/json',
      ...defaultHeadersRef.current,
      ...fetchOptions.headers,
    };

    let options = {
      ...fetchOptions,
      headers,
    };

    // Apply request interceptor if provided
    if (requestInterceptorRef.current) {
      try {
        const intercepted = await Promise.resolve(
          requestInterceptorRef.current({ url, options })
        );
        url = intercepted.url;
        options = intercepted.options;
      } catch (interceptorError) {
        return {
          data: null,
          loading: false,
          error: new Error(`Request interceptor failed: ${interceptorError.message}`),
          response: null,
        };
      }
    }

    try {
      const response = await fetch(url, options);

      // Parse response body
      let data = null;
      const contentType = response.headers.get('content-type');

      if (contentType?.includes('application/json')) {
        try {
          data = await response.json();
        } catch {
          // JSON parse failed, leave data as null
        }
      } else if (contentType?.includes('text/')) {
        data = await response.text();
      } else {
        // Try JSON first, fallback to text
        const text = await response.text();
        try {
          data = JSON.parse(text);
        } catch {
          data = text || null;
        }
      }

      // Apply response interceptor if provided
      if (responseInterceptorRef.current) {
        try {
          data = await Promise.resolve(
            responseInterceptorRef.current(response, data)
          );
        } catch (interceptorError) {
          return {
            data: null,
            loading: false,
            error: new Error(`Response interceptor failed: ${interceptorError.message}`),
            response,
          };
        }
      }

      // Handle non-2xx responses as errors
      if (!response.ok) {
        const errorMessage = data?.message || data?.error || `HTTP ${response.status}: ${response.statusText}`;
        return {
          data,
          loading: false,
          error: new Error(errorMessage),
          response,
        };
      }

      return {
        data,
        loading: false,
        error: null,
        response,
      };
    } catch (fetchError) {
      // Network errors, CORS issues, etc.
      return {
        data: null,
        loading: false,
        error: fetchError instanceof Error ? fetchError : new Error(String(fetchError)),
        response: null,
      };
    }
  }, [buildUrl]);

  /**
   * GET request
   * @param {string} path - API endpoint path
   * @param {RequestInit} [options={}] - Additional fetch options
   * @returns {Promise<ApiResponse>}
   */
  const get = useCallback((path, options = {}) => {
    return request(path, {
      ...options,
      method: 'GET',
    });
  }, [request]);

  /**
   * POST request
   * @param {string} path - API endpoint path
   * @param {*} [data] - Request body data
   * @param {RequestInit} [options={}] - Additional fetch options
   * @returns {Promise<ApiResponse>}
   */
  const post = useCallback((path, data, options = {}) => {
    return request(path, {
      ...options,
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  }, [request]);

  /**
   * PUT request
   * @param {string} path - API endpoint path
   * @param {*} [data] - Request body data
   * @param {RequestInit} [options={}] - Additional fetch options
   * @returns {Promise<ApiResponse>}
   */
  const put = useCallback((path, data, options = {}) => {
    return request(path, {
      ...options,
      method: 'PUT',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  }, [request]);

  /**
   * PATCH request
   * @param {string} path - API endpoint path
   * @param {*} [data] - Request body data
   * @param {RequestInit} [options={}] - Additional fetch options
   * @returns {Promise<ApiResponse>}
   */
  const patch = useCallback((path, data, options = {}) => {
    return request(path, {
      ...options,
      method: 'PATCH',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  }, [request]);

  /**
   * DELETE request
   * @param {string} path - API endpoint path
   * @param {RequestInit} [options={}] - Additional fetch options
   * @returns {Promise<ApiResponse>}
   */
  const del = useCallback((path, options = {}) => {
    return request(path, {
      ...options,
      method: 'DELETE',
    });
  }, [request]);

  // Memoize the API object to maintain stable reference
  const api = useMemo(() => ({
    get,
    post,
    put,
    patch,
    delete: del,
    // Expose raw request for custom methods
    request,
    // Expose baseUrl for debugging/info
    baseUrl,
  }), [get, post, put, patch, del, request, baseUrl]);

  return api;
}

export default useApi;
