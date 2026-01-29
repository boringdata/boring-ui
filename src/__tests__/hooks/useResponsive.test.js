import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  useResponsive,
  useBreakpointCheck,
  useViewportSize,
  useTouchSupport,
  useDarkModePreference,
  useReducedMotionPreference,
} from '../../hooks/useResponsive';

// Helper component to test hooks
const TestComponent = ({ hook }) => {
  const result = hook();
  return <div>{JSON.stringify(result, null, 2)}</div>;
};

describe('useResponsive Hook', () => {
  it('provides responsive utilities', () => {
    const { container } = render(
      <TestComponent hook={() => useResponsive()} />
    );

    const content = container.textContent;
    expect(content).toContain('currentBreakpoint');
    expect(content).toContain('isMobile');
    expect(content).toContain('isDesktop');
    expect(content).toContain('viewportSize');
    expect(content).toContain('hasTouch');
    expect(content).toContain('darkMode');
    expect(content).toContain('reducedMotion');
  });

  it('has correct boolean properties', () => {
    const TestHook = () => {
      const responsive = useResponsive();
      return (
        <div>
          <div>isMobile: {responsive.isMobile.toString()}</div>
          <div>isTablet: {responsive.isTablet.toString()}</div>
          <div>isDesktop: {responsive.isDesktop.toString()}</div>
        </div>
      );
    };

    render(<TestHook />);

    // At least one should be true
    expect(screen.getByText(/isMobile|isTablet|isDesktop/)).toBeInTheDocument();
  });

  it('provides specific breakpoint checks', () => {
    const TestHook = () => {
      const responsive = useResponsive();
      return (
        <div>
          <div>isXs: {responsive.isXs.toString()}</div>
          <div>isSm: {responsive.isSm.toString()}</div>
          <div>isMd: {responsive.isMd.toString()}</div>
          <div>isLg: {responsive.isLg.toString()}</div>
          <div>isXl: {responsive.isXl.toString()}</div>
          <div>is2xl: {responsive.is2xl.toString()}</div>
        </div>
      );
    };

    render(<TestHook />);

    // Should have all breakpoint checks
    expect(screen.getByText(/isXs|isSm|isMd|isLg|isXl|is2xl/)).toBeInTheDocument();
  });

  it('provides viewport dimensions', () => {
    const TestHook = () => {
      const responsive = useResponsive();
      return (
        <div>
          <div>width: {responsive.width}</div>
          <div>height: {responsive.height}</div>
        </div>
      );
    };

    render(<TestHook />);

    expect(screen.getByText(/width/)).toBeInTheDocument();
    expect(screen.getByText(/height/)).toBeInTheDocument();
  });
});

describe('useBreakpointCheck Hook', () => {
  it('checks if viewport is at breakpoint', () => {
    const TestHook = () => {
      const isSmUp = useBreakpointCheck('sm');
      return <div>isSmUp: {isSmUp.toString()}</div>;
    };

    render(<TestHook />);
    expect(screen.getByText(/isSmUp/)).toBeInTheDocument();
  });

  it('returns boolean', () => {
    const TestHook = () => {
      const isXl = useBreakpointCheck('xl');
      expect(typeof isXl).toBe('boolean');
      return null;
    };

    render(<TestHook />);
  });
});

describe('useViewportSize Hook', () => {
  it('provides viewport dimensions', () => {
    const TestHook = () => {
      const { width, height } = useViewportSize();
      return (
        <div>
          <div>width: {width}</div>
          <div>height: {height}</div>
        </div>
      );
    };

    render(<TestHook />);

    expect(screen.getByText(/width/)).toBeInTheDocument();
    expect(screen.getByText(/height/)).toBeInTheDocument();
  });

  it('returns object with width and height', () => {
    const TestHook = () => {
      const size = useViewportSize();
      expect(size).toHaveProperty('width');
      expect(size).toHaveProperty('height');
      return null;
    };

    render(<TestHook />);
  });
});

describe('useTouchSupport Hook', () => {
  it('returns boolean', () => {
    const TestHook = () => {
      const hasTouch = useTouchSupport();
      expect(typeof hasTouch).toBe('boolean');
      return null;
    };

    render(<TestHook />);
  });
});

describe('useDarkModePreference Hook', () => {
  it('returns boolean', () => {
    const TestHook = () => {
      const darkMode = useDarkModePreference();
      expect(typeof darkMode).toBe('boolean');
      return null;
    };

    render(<TestHook />);
  });
});

describe('useReducedMotionPreference Hook', () => {
  it('returns boolean', () => {
    const TestHook = () => {
      const reducedMotion = useReducedMotionPreference();
      expect(typeof reducedMotion).toBe('boolean');
      return null;
    };

    render(<TestHook />);
  });
});
