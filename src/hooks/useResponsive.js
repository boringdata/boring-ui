import { useEffect, useState, useCallback } from 'react';
import {
  useBreakpoint,
  getCurrentBreakpoint,
  supportsTouchEvents,
  prefersDarkMode,
  prefersReducedMotion,
  getViewportSize,
  onBreakpointChange,
} from '../utils/responsive';

/**
 * useResponsive Hook
 * Provides responsive design utilities
 *
 * @returns {Object} Responsive utilities
 *
 * @example
 * ```jsx
 * function MyComponent() {
 *   const { isMobile, isTablet, currentBreakpoint } = useResponsive();
 *
 *   return (
 *     <div>
 *       {isMobile && <MobileNav />}
 *       {!isMobile && <DesktopNav />}
 *     </div>
 *   );
 * }
 * ```
 */
export function useResponsive() {
  const [currentBreakpoint, setCurrentBreakpoint] = useState('xs');
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const [hasTouch, setHasTouch] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  // Initialize values
  useEffect(() => {
    setCurrentBreakpoint(getCurrentBreakpoint());
    setViewportSize(getViewportSize());
    setHasTouch(supportsTouchEvents());
    setDarkMode(prefersDarkMode());
    setReducedMotion(prefersReducedMotion());
  }, []);

  // Listen to breakpoint changes
  useEffect(() => {
    const handleResize = () => {
      setCurrentBreakpoint(getCurrentBreakpoint());
      setViewportSize(getViewportSize());
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Listen to dark mode changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => setDarkMode(e.matches);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  // Listen to reduced motion changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e) => setReducedMotion(e.matches);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return {
    // Current breakpoint
    currentBreakpoint,
    isMobile: currentBreakpoint === 'xs' || currentBreakpoint === 'sm',
    isTablet: currentBreakpoint === 'md' || currentBreakpoint === 'lg',
    isDesktop: currentBreakpoint === 'xl' || currentBreakpoint === '2xl',

    // Specific breakpoints
    isXs: currentBreakpoint === 'xs',
    isSm: currentBreakpoint === 'sm',
    isMd: currentBreakpoint === 'md',
    isLg: currentBreakpoint === 'lg',
    isXl: currentBreakpoint === 'xl',
    is2xl: currentBreakpoint === '2xl',

    // Viewport info
    viewportSize,
    width: viewportSize.width,
    height: viewportSize.height,

    // Device capabilities
    hasTouch,
    darkMode,
    reducedMotion,
  };
}

/**
 * useBreakpointCheck Hook
 * Check if viewport matches a specific breakpoint
 *
 * @param {string} breakpoint - Breakpoint name (xs, sm, md, lg, xl, 2xl)
 * @returns {boolean} Whether viewport matches breakpoint
 *
 * @example
 * ```jsx
 * const isMobile = useBreakpointCheck('sm');
 * ```
 */
export function useBreakpointCheck(breakpoint) {
  const [isAt, setIsAt] = useState(() => useBreakpoint(breakpoint));

  useEffect(() => {
    // Initial check
    setIsAt(useBreakpoint(breakpoint));

    // Listen to changes
    const cleanup = onBreakpointChange(breakpoint, (matches) => {
      setIsAt(matches);
    });

    // Also listen to resize for immediate updates
    const handleResize = () => {
      setIsAt(useBreakpoint(breakpoint));
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cleanup();
      window.removeEventListener('resize', handleResize);
    };
  }, [breakpoint]);

  return isAt;
}

/**
 * useViewportSize Hook
 * Get current viewport dimensions
 *
 * @returns {Object} {width, height}
 *
 * @example
 * ```jsx
 * const { width, height } = useViewportSize();
 * ```
 */
export function useViewportSize() {
  const [size, setSize] = useState(() => getViewportSize());

  useEffect(() => {
    const handleResize = () => {
      setSize(getViewportSize());
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return size;
}

/**
 * useTouchSupport Hook
 * Check if device supports touch
 *
 * @returns {boolean} Whether device supports touch
 *
 * @example
 * ```jsx
 * const hasTouch = useTouchSupport();
 * ```
 */
export function useTouchSupport() {
  const [hasTouch, setHasTouch] = useState(() => supportsTouchEvents());

  // No need to re-check, touch support doesn't change
  return hasTouch;
}

/**
 * useDarkModePreference Hook
 * Check if device prefers dark mode
 *
 * @returns {boolean} Whether device prefers dark mode
 *
 * @example
 * ```jsx
 * const isDarkMode = useDarkModePreference();
 * ```
 */
export function useDarkModePreference() {
  const [darkMode, setDarkMode] = useState(() => prefersDarkMode());

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => setDarkMode(e.matches);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return darkMode;
}

/**
 * useReducedMotionPreference Hook
 * Check if device prefers reduced motion
 *
 * @returns {boolean} Whether device prefers reduced motion
 *
 * @example
 * ```jsx
 * const prefersReducedMotion = useReducedMotionPreference();
 * ```
 */
export function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(() => prefersReducedMotion());

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e) => setReducedMotion(e.matches);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return reducedMotion;
}

export default useResponsive;
