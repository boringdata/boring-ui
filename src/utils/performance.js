/**
 * Performance Optimization Utilities
 * Tools for measuring and optimizing app performance
 */

/**
 * Measure component render time
 * @param {string} componentName - Name of component
 * @param {Function} callback - Component render function
 * @returns {*} Render result
 */
export function measureRender(componentName, callback) {
  const start = performance.now();
  const result = callback();
  const end = performance.now();

  if (process.env.NODE_ENV === 'development') {
    console.log(`${componentName} rendered in ${(end - start).toFixed(2)}ms`);
  }

  return result;
}

/**
 * Measure operation time
 * @param {string} name - Operation name
 * @param {Function} callback - Operation function
 * @returns {*} Operation result
 */
export function measurePerformance(name, callback) {
  const start = performance.now();
  const result = callback();
  const end = performance.now();

  const duration = end - start;
  if (process.env.NODE_ENV === 'development') {
    const level = duration > 16 ? 'warn' : 'log';
    console[level](`${name}: ${duration.toFixed(2)}ms`);
  }

  return result;
}

/**
 * Debounce function calls
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(fn, delay) {
  let timeoutId;

  return function debounced(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Throttle function calls
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @returns {Function} Throttled function
 */
export function throttle(fn, limit) {
  let inThrottle;

  return function throttled(...args) {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Request idle callback polyfill
 * @param {Function} callback - Callback function
 * @returns {number} ID for cancellation
 */
export function requestIdleCallback(callback) {
  if (typeof window !== 'undefined' && window.requestIdleCallback) {
    return window.requestIdleCallback(callback);
  }

  const start = Date.now();
  return setTimeout(() => {
    callback({
      didTimeout: false,
      timeRemaining: () => Math.max(0, 50 - (Date.now() - start)),
    });
  }, 1);
}

/**
 * Request animation frame helper
 * @param {Function} callback - Callback function
 * @returns {number} Frame ID
 */
export function nextFrame(callback) {
  if (typeof window !== 'undefined' && window.requestAnimationFrame) {
    return window.requestAnimationFrame(callback);
  }

  return setTimeout(callback, 16); // ~60fps
}

/**
 * Lazy load component dynamically
 * @param {Function} importFn - Dynamic import function
 * @returns {Promise<Module>} Module promise
 */
export async function lazyLoadComponent(importFn) {
  return new Promise((resolve, reject) => {
    requestIdleCallback(() => {
      importFn()
        .then(resolve)
        .catch(reject);
    });
  });
}

/**
 * Preload image
 * @param {string} src - Image source URL
 * @returns {Promise<HTMLImageElement>} Image element
 */
export function preloadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/**
 * Get Web Vitals metrics
 * @returns {Object} Metrics object
 */
export function getWebVitals() {
  if (typeof window === 'undefined') {
    return null;
  }

  const vitals = {
    pageLoadTime: performance.timing.loadEventEnd - performance.timing.navigationStart,
    domContentLoadedTime: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart,
    resourceLoadTime: performance.timing.responseEnd - performance.timing.fetchStart,
  };

  // Largest Contentful Paint
  if (typeof window.PerformanceObserver !== 'undefined') {
    try {
      const observer = new window.PerformanceObserver((list) => {
        const lastEntry = list.getEntries().pop();
        vitals.lcp = lastEntry?.renderTime || lastEntry?.loadTime;
      });
      observer.observe({ entryTypes: ['largest-contentful-paint'] });
    } catch (e) {
      // LCP not supported
    }
  }

  return vitals;
}

/**
 * Report Web Vitals to analytics
 * @param {Object} vitals - Vitals metrics
 * @param {string} endpoint - Analytics endpoint
 */
export async function reportWebVitals(vitals, endpoint) {
  if (!endpoint) return;

  try {
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(vitals),
      keepalive: true, // Keep connection alive for reliability
    });
  } catch (error) {
    console.error('Failed to report metrics:', error);
  }
}

/**
 * Analyze bundle size
 * @returns {Object} Bundle metrics
 */
export function analyzeBundleSize() {
  if (typeof window === 'undefined') {
    return null;
  }

  return {
    navigationEntries: performance.getEntriesByType('navigation'),
    resourceEntries: performance.getEntriesByType('resource'),
    totalSize: performance.getEntriesByType('resource').reduce(
      (total, entry) => total + (entry.transferSize || 0),
      0
    ),
  };
}

/**
 * Create performance observer
 * @param {string} entryType - Entry type to observe
 * @param {Function} callback - Callback function
 * @returns {PerformanceObserver|null} Observer instance
 */
export function createPerformanceObserver(entryType, callback) {
  if (typeof window === 'undefined' || !window.PerformanceObserver) {
    return null;
  }

  try {
    const observer = new window.PerformanceObserver((list) => {
      const entries = list.getEntries();
      callback(entries);
    });

    observer.observe({ entryTypes: [entryType] });
    return observer;
  } catch (error) {
    console.warn(`Performance observer for ${entryType} not supported:`, error);
    return null;
  }
}

/**
 * Check if device is slow
 * @returns {boolean} True if on slow connection or slow device
 */
export function isSlowDevice() {
  if (typeof navigator === 'undefined') {
    return false;
  }

  // Check connection speed
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (connection) {
    const effectiveType = connection.effectiveType;
    if (effectiveType === '2g' || effectiveType === '3g') {
      return true;
    }
  }

  // Check device memory
  if (navigator.deviceMemory && navigator.deviceMemory < 4) {
    return true;
  }

  return false;
}

/**
 * Cache data with expiration
 * @param {string} key - Cache key
 * @param {*} value - Value to cache
 * @param {number} ttl - Time to live in milliseconds
 */
export function setCache(key, value, ttl = 60000) {
  const cache = JSON.parse(sessionStorage.getItem('__cache__') || '{}');
  cache[key] = {
    value,
    expires: Date.now() + ttl,
  };
  sessionStorage.setItem('__cache__', JSON.stringify(cache));
}

/**
 * Get cached data
 * @param {string} key - Cache key
 * @returns {*} Cached value or null
 */
export function getCache(key) {
  const cache = JSON.parse(sessionStorage.getItem('__cache__') || '{}');
  const item = cache[key];

  if (!item) return null;

  if (Date.now() > item.expires) {
    delete cache[key];
    sessionStorage.setItem('__cache__', JSON.stringify(cache));
    return null;
  }

  return item.value;
}

/**
 * Clear cache
 * @param {string} [key] - Optional specific key to clear
 */
export function clearCache(key) {
  if (!key) {
    sessionStorage.removeItem('__cache__');
    return;
  }

  const cache = JSON.parse(sessionStorage.getItem('__cache__') || '{}');
  delete cache[key];
  sessionStorage.setItem('__cache__', JSON.stringify(cache));
}
