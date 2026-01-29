/**
 * Responsive Design Utilities
 * Mobile-first breakpoints and responsive helpers
 */

/**
 * Tailwind breakpoints (mobile-first)
 */
export const BREAKPOINTS = {
  xs: 0,      // Extra small (default)
  sm: 640,    // Small (width >= 640px)
  md: 768,    // Medium (width >= 768px)
  lg: 1024,   // Large (width >= 1024px)
  xl: 1280,   // Extra large (width >= 1280px)
  '2xl': 1536, // 2X large (width >= 1536px)
};

/**
 * Tailwind breakpoint names
 */
export const BREAKPOINT_NAMES = Object.keys(BREAKPOINTS);

/**
 * Check if current viewport is at or above breakpoint
 * @param {string} breakpoint - Breakpoint name (xs, sm, md, lg, xl, 2xl)
 * @returns {boolean} Whether viewport is at or above breakpoint
 */
export function useBreakpoint(breakpoint) {
  if (typeof window === 'undefined') return false;

  const width = window.innerWidth;
  const breakpointValue = BREAKPOINTS[breakpoint];

  if (breakpointValue === undefined) {
    console.warn(`Unknown breakpoint: ${breakpoint}`);
    return false;
  }

  return width >= breakpointValue;
}

/**
 * Get current breakpoint name
 * @returns {string} Current breakpoint (xs, sm, md, lg, xl, 2xl)
 */
export function getCurrentBreakpoint() {
  if (typeof window === 'undefined') return 'xs';

  const width = window.innerWidth;

  // Iterate from largest to smallest
  const names = [...BREAKPOINT_NAMES].reverse();
  for (const name of names) {
    if (width >= BREAKPOINTS[name]) {
      return name;
    }
  }

  return 'xs';
}

/**
 * Touch target size constant
 * WCAG 2.1 Level AAA: 44x44px minimum
 */
export const TOUCH_TARGET_SIZE = 44;

/**
 * Check if device supports touch
 * @returns {boolean} Whether device supports touch
 */
export function supportsTouchEvents() {
  if (typeof window === 'undefined') return false;

  return (
    typeof window.ontouchstart !== 'undefined' ||
    typeof window.onmsgesturechange !== 'undefined' ||
    navigator.maxTouchPoints > 0
  );
}

/**
 * Check if device is in dark mode
 * @returns {boolean} Whether device prefers dark mode
 */
export function prefersDarkMode() {
  if (typeof window === 'undefined') return false;

  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Check if device prefers reduced motion
 * @returns {boolean} Whether device prefers reduced motion
 */
export function prefersReducedMotion() {
  if (typeof window === 'undefined') return false;

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Get viewport dimensions
 * @returns {Object} {width, height}
 */
export function getViewportSize() {
  if (typeof window === 'undefined') {
    return { width: 0, height: 0 };
  }

  return {
    width: window.innerWidth,
    height: window.innerHeight,
  };
}

/**
 * Create responsive class names
 * @param {Object} config - Breakpoint -> class mapping
 * @returns {string} Space-separated class names
 *
 * @example
 * ```js
 * createResponsiveClasses({
 *   xs: 'px-2 text-sm',
 *   md: 'px-4 text-base',
 *   lg: 'px-6 text-lg'
 * })
 * ```
 */
export function createResponsiveClasses(config) {
  const classes = [];

  for (const [breakpoint, classNames] of Object.entries(config)) {
    if (breakpoint === 'xs') {
      classes.push(classNames);
    } else {
      classes.push(`${breakpoint}:${classNames}`);
    }
  }

  return classes.join(' ');
}

/**
 * Responsive media query listener hook setup
 * @param {string} breakpoint - Breakpoint to listen for
 * @param {Function} callback - Callback function
 * @returns {Function} Cleanup function
 */
export function onBreakpointChange(breakpoint, callback) {
  if (typeof window === 'undefined') return () => {};

  const breakpointValue = BREAKPOINTS[breakpoint];
  if (breakpointValue === undefined) {
    console.warn(`Unknown breakpoint: ${breakpoint}`);
    return () => {};
  }

  const mediaQuery = window.matchMedia(`(min-width: ${breakpointValue}px)`);
  const handleChange = (e) => callback(e.matches);

  // Modern browsers
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }

  // Older browsers
  mediaQuery.addListener(handleChange);
  return () => mediaQuery.removeListener(handleChange);
}

/**
 * Get safe area insets for notch/safe zones
 * @returns {Object} {top, right, bottom, left}
 */
export function getSafeAreaInsets() {
  if (typeof window === 'undefined') {
    return { top: 0, right: 0, bottom: 0, left: 0 };
  }

  const insets = {
    top: parseInt(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-inset-top'
      ) || '0'
    ),
    right: parseInt(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-inset-right'
      ) || '0'
    ),
    bottom: parseInt(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-inset-bottom'
      ) || '0'
    ),
    left: parseInt(
      getComputedStyle(document.documentElement).getPropertyValue(
        '--safe-area-inset-left'
      ) || '0'
    ),
  };

  return insets;
}

/**
 * Format bytes for responsive display
 * @param {number} bytes - Number of bytes
 * @returns {string} Formatted string (10 KB, 1.5 MB, etc.)
 */
export function formatBytes(bytes) {
  if (!bytes) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round((bytes / Math.pow(k, i)) * 10) / 10 + ' ' + sizes[i];
}

/**
 * Check if horizontal scroll is visible
 * @returns {boolean} Whether document has horizontal scrollbar
 */
export function hasHorizontalScroll() {
  if (typeof document === 'undefined') return false;

  return document.documentElement.scrollWidth > document.documentElement.clientWidth;
}
