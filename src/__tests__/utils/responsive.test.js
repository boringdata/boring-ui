import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  BREAKPOINTS,
  useBreakpoint,
  getCurrentBreakpoint,
  supportsTouchEvents,
  prefersDarkMode,
  prefersReducedMotion,
  getViewportSize,
  TOUCH_TARGET_SIZE,
  createResponsiveClasses,
  hasHorizontalScroll,
} from '../../utils/responsive';

describe('Responsive Utilities', () => {
  describe('BREAKPOINTS', () => {
    it('has all breakpoint values', () => {
      expect(BREAKPOINTS.xs).toBe(0);
      expect(BREAKPOINTS.sm).toBe(640);
      expect(BREAKPOINTS.md).toBe(768);
      expect(BREAKPOINTS.lg).toBe(1024);
      expect(BREAKPOINTS.xl).toBe(1280);
      expect(BREAKPOINTS['2xl']).toBe(1536);
    });
  });

  describe('TOUCH_TARGET_SIZE', () => {
    it('meets WCAG AAA minimum', () => {
      expect(TOUCH_TARGET_SIZE).toBe(44);
    });
  });

  describe('useBreakpoint', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1024,
      });
    });

    it('returns true for current breakpoint and below', () => {
      expect(useBreakpoint('lg')).toBe(true);
      expect(useBreakpoint('md')).toBe(true);
      expect(useBreakpoint('sm')).toBe(true);
      expect(useBreakpoint('xs')).toBe(true);
    });

    it('returns false for breakpoints above current', () => {
      expect(useBreakpoint('xl')).toBe(false);
      expect(useBreakpoint('2xl')).toBe(false);
    });

    it('handles unknown breakpoints gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation();
      expect(useBreakpoint('unknown')).toBe(false);
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('getCurrentBreakpoint', () => {
    it('returns correct breakpoint for 640px', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 640,
      });
      expect(getCurrentBreakpoint()).toBe('sm');
    });

    it('returns correct breakpoint for 768px', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 768,
      });
      expect(getCurrentBreakpoint()).toBe('md');
    });

    it('returns xs for small screens', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 320,
      });
      expect(getCurrentBreakpoint()).toBe('xs');
    });

    it('returns 2xl for very large screens', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1920,
      });
      expect(getCurrentBreakpoint()).toBe('2xl');
    });
  });

  describe('supportsTouchEvents', () => {
    it('returns boolean', () => {
      const result = supportsTouchEvents();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('prefersDarkMode', () => {
    it('returns boolean', () => {
      const result = prefersDarkMode();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('prefersReducedMotion', () => {
    it('returns boolean', () => {
      const result = prefersReducedMotion();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('getViewportSize', () => {
    it('returns object with width and height', () => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1024,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        configurable: true,
        value: 768,
      });

      const size = getViewportSize();
      expect(size).toHaveProperty('width', 1024);
      expect(size).toHaveProperty('height', 768);
    });
  });

  describe('createResponsiveClasses', () => {
    it('creates responsive class string', () => {
      const result = createResponsiveClasses({
        xs: 'px-2 text-sm',
        md: 'px-4 text-base',
        lg: 'px-6 text-lg',
      });

      expect(result).toContain('px-2 text-sm');
      expect(result).toContain('md:px-4 text-base');
      expect(result).toContain('lg:px-6 text-lg');
    });

    it('handles single breakpoint', () => {
      const result = createResponsiveClasses({
        xs: 'p-4',
      });

      expect(result).toBe('p-4');
    });
  });

  describe('hasHorizontalScroll', () => {
    it('returns boolean', () => {
      const result = hasHorizontalScroll();
      expect(typeof result).toBe('boolean');
    });
  });
});
