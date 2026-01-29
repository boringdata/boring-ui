/**
 * Lazy Component Loading Utilities
 * Tools for code splitting and lazy loading components
 */

import { lazy, Suspense } from 'react';

/**
 * Wrap component with Suspense and fallback
 * @param {Function} importFn - Dynamic import function
 * @param {React.ReactNode} fallback - Fallback component
 * @returns {React.Component} Wrapped component
 */
export function withSuspense(importFn, fallback = null) {
  const LazyComponent = lazy(importFn);

  return function SuspenseWrapper(props) {
    return (
      <Suspense fallback={fallback}>
        <LazyComponent {...props} />
      </Suspense>
    );
  };
}

/**
 * Lazy load component with error boundary
 * @param {Function} importFn - Dynamic import function
 * @param {React.ReactNode} fallback - Fallback component
 * @param {React.ReactNode} errorComponent - Error component
 * @returns {React.Component} Wrapped component
 */
export function withLazyLoad(importFn, fallback = null, errorComponent = null) {
  let component = lazy(importFn);

  return function LazyLoadWrapper(props) {
    return (
      <Suspense fallback={fallback}>
        <component {...props} />
      </Suspense>
    );
  };
}

/**
 * Lazy route components
 * Pre-configured lazy loaders for common routes
 */
export const lazyRoutes = {
  /**
   * Editor component
   */
  Editor: () => lazy(() => import('../components/Editor')),

  /**
   * Terminal component
   */
  Terminal: () => lazy(() => import('../components/Terminal')),

  /**
   * Chat component
   */
  Chat: () => lazy(() => import('../components/chat')),

  /**
   * Settings page
   */
  Settings: () => lazy(() => import('../components/Settings')),

  /**
   * Help page
   */
  Help: () => lazy(() => import('../components/Help')),
};

/**
 * Create lazy-loaded modal
 * @param {Function} importFn - Dynamic import function
 * @returns {React.Component} Modal component
 */
export function lazyModal(importFn) {
  return withSuspense(importFn);
}

/**
 * Preload lazy component
 * @param {Function} importFn - Dynamic import function
 */
export function preloadComponent(importFn) {
  if (typeof window !== 'undefined') {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(() => importFn());
    } else {
      setTimeout(() => importFn(), 2000);
    }
  }
}

/**
 * Create route-based code splitting
 * @param {Object} routes - Route configuration
 * @returns {Object} Routes with lazy components
 *
 * @example
 * ```js
 * const routes = createLazyRoutes({
 *   '/editor': () => import('../pages/Editor'),
 *   '/terminal': () => import('../pages/Terminal'),
 * });
 * ```
 */
export function createLazyRoutes(routes) {
  const lazyRoutes = {};

  for (const [path, importFn] of Object.entries(routes)) {
    lazyRoutes[path] = withSuspense(importFn);
  }

  return lazyRoutes;
}

/**
 * Image lazy loading helper
 * @param {string} src - Image source
 * @param {string} [placeholder] - Placeholder image
 * @returns {Object} Image props
 *
 * @example
 * ```jsx
 * <img {...lazyImage('/large-image.jpg', '/thumbnail.jpg')} />
 * ```
 */
export function lazyImage(src, placeholder) {
  if (!('IntersectionObserver' in window)) {
    // Fallback for browsers without IntersectionObserver
    return { src, loading: 'lazy' };
  }

  return {
    'data-src': src,
    src: placeholder || 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
    loading: 'lazy',
  };
}

/**
 * Script lazy loading
 * @param {string} src - Script source
 * @param {Object} options - Script options
 * @returns {Promise<void>} Load promise
 */
export function lazyScript(src, options = {}) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;

    if (options.defer) {
      script.defer = true;
    }

    if (options.module) {
      script.type = 'module';
    }

    script.onload = resolve;
    script.onerror = reject;

    document.head.appendChild(script);
  });
}

/**
 * CSS lazy loading
 * @param {string} href - Stylesheet href
 * @returns {Promise<void>} Load promise
 */
export function lazyCSS(href) {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;

    link.onload = resolve;
    link.onerror = reject;

    document.head.appendChild(link);
  });
}

/**
 * Font lazy loading
 * @param {string} name - Font family name
 * @param {string} url - Font file URL
 * @returns {Promise<void>} Load promise
 */
export function lazyFont(name, url) {
  if (!('FontFace' in window)) {
    return Promise.reject(new Error('FontFace API not supported'));
  }

  const font = new FontFace(name, `url(${url})`);
  return font
    .load()
    .then((loadedFont) => {
      document.fonts.add(loadedFont);
    });
}

/**
 * Optimize list rendering with virtualization
 * Use with react-window or react-virtual for large lists
 * @param {Array} items - Items to render
 * @param {number} itemSize - Height of each item
 * @param {number} containerHeight - Container height
 * @returns {Object} Visible items
 */
export function calculateVisibleItems(items, itemSize, containerHeight) {
  const visibleCount = Math.ceil(containerHeight / itemSize) + 1;
  const scrollPosition = containerHeight;
  const startIndex = Math.max(0, Math.floor(scrollPosition / itemSize) - 1);
  const endIndex = Math.min(items.length, startIndex + visibleCount);

  return {
    startIndex,
    endIndex,
    visibleItems: items.slice(startIndex, endIndex),
  };
}

export default {
  withSuspense,
  withLazyLoad,
  lazyRoutes,
  lazyModal,
  preloadComponent,
  createLazyRoutes,
  lazyImage,
  lazyScript,
  lazyCSS,
  lazyFont,
  calculateVisibleItems,
};
