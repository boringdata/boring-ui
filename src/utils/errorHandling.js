/**
 * Error Handling Utilities
 * Provides error classification, messaging, and recovery suggestions
 */

/**
 * Error type classifications
 */
export const ERROR_TYPES = {
  NETWORK: 'network',
  OFFLINE: 'offline',
  TIMEOUT: 'timeout',
  CLIENT_ERROR: 'client_error', // 4xx
  SERVER_ERROR: 'server_error', // 5xx
  VALIDATION: 'validation',
  UNKNOWN: 'unknown',
};

/**
 * Classify an error by type
 * @param {Error} error - The error to classify
 * @param {number} statusCode - Optional HTTP status code
 * @returns {string} Error type from ERROR_TYPES
 */
export function classifyError(error, statusCode = null) {
  if (!error) {
    return ERROR_TYPES.UNKNOWN;
  }

  const message = error.message || String(error);

  // Check for network-related errors
  if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
    return ERROR_TYPES.NETWORK;
  }

  if (message.includes('offline') || message.includes('Offline')) {
    return ERROR_TYPES.OFFLINE;
  }

  if (message.includes('timeout') || message.includes('Timeout')) {
    return ERROR_TYPES.TIMEOUT;
  }

  if (message.includes('validation')) {
    return ERROR_TYPES.VALIDATION;
  }

  // Check HTTP status codes
  if (statusCode) {
    if (statusCode >= 400 && statusCode < 500) {
      return ERROR_TYPES.CLIENT_ERROR;
    }
    if (statusCode >= 500) {
      return ERROR_TYPES.SERVER_ERROR;
    }
  }

  return ERROR_TYPES.UNKNOWN;
}

/**
 * Get user-friendly error message
 * @param {Error} error - The error
 * @param {string} errorType - Error type (from classifyError)
 * @returns {Object} Message and recovery suggestions
 */
export function getErrorMessage(error, errorType = null) {
  const type = errorType || classifyError(error);
  const defaultMessage = error?.message || 'An unexpected error occurred';

  const messages = {
    [ERROR_TYPES.NETWORK]: {
      title: 'Connection Error',
      message: 'Unable to connect to the server. Please check your internet connection.',
      suggestions: [
        'Check your internet connection',
        'Verify the server is online',
        'Try again in a few moments',
      ],
    },
    [ERROR_TYPES.OFFLINE]: {
      title: 'You are Offline',
      message: 'Your device is currently offline. Some features may be unavailable.',
      suggestions: [
        'Check your internet connection',
        'Wait for connection to be restored',
      ],
    },
    [ERROR_TYPES.TIMEOUT]: {
      title: 'Request Timeout',
      message: 'The request took too long to complete. Please try again.',
      suggestions: [
        'Check your internet connection',
        'Try again with a simpler request',
        'Contact support if the problem persists',
      ],
    },
    [ERROR_TYPES.CLIENT_ERROR]: {
      title: 'Invalid Request',
      message: defaultMessage,
      suggestions: [
        'Check that all required fields are filled',
        'Verify the input format is correct',
        'Reload the page and try again',
      ],
    },
    [ERROR_TYPES.SERVER_ERROR]: {
      title: 'Server Error',
      message: 'The server encountered an error. Our team has been notified.',
      suggestions: [
        'Try again in a few moments',
        'Contact support if the problem persists',
      ],
    },
    [ERROR_TYPES.VALIDATION]: {
      title: 'Validation Error',
      message: defaultMessage,
      suggestions: [
        'Check that all required fields are filled',
        'Verify the input format is correct',
      ],
    },
    [ERROR_TYPES.UNKNOWN]: {
      title: 'Something Went Wrong',
      message: defaultMessage,
      suggestions: [
        'Try refreshing the page',
        'Clear your browser cache',
        'Contact support if the problem persists',
      ],
    },
  };

  return messages[type] || messages[ERROR_TYPES.UNKNOWN];
}

/**
 * Check if error is retryable
 * @param {Error} error - The error
 * @param {string} errorType - Error type
 * @param {number} statusCode - HTTP status code
 * @returns {boolean} Whether the error is retryable
 */
export function isRetryableError(error, errorType = null, statusCode = null) {
  const type = errorType || classifyError(error, statusCode);

  // Retryable error types
  const retryableTypes = [
    ERROR_TYPES.NETWORK,
    ERROR_TYPES.OFFLINE,
    ERROR_TYPES.TIMEOUT,
    ERROR_TYPES.SERVER_ERROR, // 5xx errors
  ];

  return retryableTypes.includes(type);
}

/**
 * Calculate exponential backoff delay
 * @param {number} attempt - Attempt number (0-indexed)
 * @param {number} baseDelay - Base delay in ms (default 1000)
 * @param {number} maxDelay - Maximum delay in ms (default 30000)
 * @returns {number} Delay in milliseconds
 */
export function getRetryDelay(attempt, baseDelay = 1000, maxDelay = 30000) {
  const delay = baseDelay * Math.pow(2, attempt);
  const jittered = delay + Math.random() * 1000; // Add jitter
  return Math.min(jittered, maxDelay);
}

/**
 * Retry a function with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {Object} options - Retry options
 * @param {number} options.maxAttempts - Maximum retry attempts (default 3)
 * @param {number} options.baseDelay - Base delay in ms (default 1000)
 * @param {number} options.maxDelay - Maximum delay in ms (default 30000)
 * @param {Function} options.shouldRetry - Function to determine if error is retryable
 * @returns {Promise<*>} Result of function
 */
export async function retryWithBackoff(fn, options = {}) {
  const {
    maxAttempts = 3,
    baseDelay = 1000,
    maxDelay = 30000,
    shouldRetry = isRetryableError,
  } = options;

  let lastError = null;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const errorType = classifyError(error);

      // Check if we should retry
      if (attempt < maxAttempts - 1 && shouldRetry(error, errorType)) {
        const delay = getRetryDelay(attempt, baseDelay, maxDelay);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      throw error;
    }
  }

  throw lastError;
}

/**
 * Create a safe error object
 * @param {*} error - Error value
 * @param {Object} context - Additional context
 * @returns {Object} Safe error object
 */
export function createErrorObject(error, context = {}) {
  const isError = error instanceof Error;
  const type = classifyError(error, context.statusCode);
  const { title, message, suggestions } = getErrorMessage(error, type);

  return {
    // Core error info
    message: isError ? error.message : String(error),
    name: isError ? error.name : 'Error',
    type,

    // User-friendly info
    title,
    userMessage: message,
    suggestions,

    // Context
    timestamp: new Date().toISOString(),
    context: {
      statusCode: context.statusCode,
      endpoint: context.endpoint,
      method: context.method,
      ...context,
    },

    // Stack trace (preserved for debugging)
    stack: isError ? error.stack : undefined,

    // Recovery methods
    isRetryable: isRetryableError(error, type, context.statusCode),
    canDismiss: !isRetryableError(error, type, context.statusCode),
  };
}

/**
 * Log error for debugging
 * @param {Error} error - Error to log
 * @param {Object} context - Additional context
 */
export function logError(error, context = {}) {
  const errorObj = createErrorObject(error, context);

  // In production, send to error tracking service
  if (process.env.NODE_ENV === 'production') {
    // Example: sendToErrorTracking(errorObj)
    console.error('[Error Logged]', {
      message: errorObj.message,
      type: errorObj.type,
      context: errorObj.context,
      timestamp: errorObj.timestamp,
    });
  } else {
    // In development, log full details
    console.error('[Error]', errorObj);
  }
}

/**
 * Check if browser is online
 * @returns {boolean} Whether browser is online
 */
export function isOnline() {
  return typeof navigator !== 'undefined' && navigator.onLine;
}

/**
 * Format error for display
 * @param {Error} error - Error to format
 * @returns {Object} Formatted error info
 */
export function formatErrorForDisplay(error) {
  const errorObj = createErrorObject(error);
  return {
    icon: getErrorIcon(errorObj.type),
    title: errorObj.title,
    message: errorObj.userMessage,
    suggestions: errorObj.suggestions,
    isRetryable: errorObj.isRetryable,
    canDismiss: errorObj.canDismiss,
  };
}

/**
 * Get icon name for error type
 * @param {string} errorType - Error type
 * @returns {string} Icon name
 */
export function getErrorIcon(errorType) {
  const icons = {
    [ERROR_TYPES.NETWORK]: 'WifiOff',
    [ERROR_TYPES.OFFLINE]: 'WifiOff',
    [ERROR_TYPES.TIMEOUT]: 'Clock',
    [ERROR_TYPES.CLIENT_ERROR]: 'AlertCircle',
    [ERROR_TYPES.SERVER_ERROR]: 'AlertTriangle',
    [ERROR_TYPES.VALIDATION]: 'CheckX',
    [ERROR_TYPES.UNKNOWN]: 'AlertCircle',
  };

  return icons[errorType] || 'AlertCircle';
}
