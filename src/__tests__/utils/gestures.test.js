import { describe, it, expect, vi, beforeEach } from 'vitest';
import { detectSwipe, detectLongPress, useSwipe, useLongPress } from '../../utils/gestures';

describe('Gesture Utilities', () => {
  let element;

  beforeEach(() => {
    element = document.createElement('div');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  describe('detectSwipe', () => {
    it('detects left swipe', (done) => {
      const callback = vi.fn();
      const callbacks = {
        onSwipeLeft: callback,
      };

      detectSwipe(element, callbacks, 50);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 100, clientY: 50 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 30, clientY: 50 }],
      });

      element.dispatchEvent(touchStartEvent);
      element.dispatchEvent(touchEndEvent);

      setTimeout(() => {
        expect(callback).toHaveBeenCalled();
        done();
      }, 10);
    });

    it('detects right swipe', (done) => {
      const callback = vi.fn();
      const callbacks = {
        onSwipeRight: callback,
      };

      detectSwipe(element, callbacks, 50);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 30, clientY: 50 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 100, clientY: 50 }],
      });

      element.dispatchEvent(touchStartEvent);
      element.dispatchEvent(touchEndEvent);

      setTimeout(() => {
        expect(callback).toHaveBeenCalled();
        done();
      }, 10);
    });

    it('detects up swipe', (done) => {
      const callback = vi.fn();
      const callbacks = {
        onSwipeUp: callback,
      };

      detectSwipe(element, callbacks, 50);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 100 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 50, clientY: 30 }],
      });

      element.dispatchEvent(touchStartEvent);
      element.dispatchEvent(touchEndEvent);

      setTimeout(() => {
        expect(callback).toHaveBeenCalled();
        done();
      }, 10);
    });

    it('detects down swipe', (done) => {
      const callback = vi.fn();
      const callbacks = {
        onSwipeDown: callback,
      };

      detectSwipe(element, callbacks, 50);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 30 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 50, clientY: 100 }],
      });

      element.dispatchEvent(touchStartEvent);
      element.dispatchEvent(touchEndEvent);

      setTimeout(() => {
        expect(callback).toHaveBeenCalled();
        done();
      }, 10);
    });

    it('respects threshold', (done) => {
      const callback = vi.fn();
      const callbacks = {
        onSwipeLeft: callback,
      };

      detectSwipe(element, callbacks, 100); // High threshold

      // Swipe less than threshold
      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 100, clientY: 50 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        changedTouches: [{ clientX: 80, clientY: 50 }],
      });

      element.dispatchEvent(touchStartEvent);
      element.dispatchEvent(touchEndEvent);

      setTimeout(() => {
        expect(callback).not.toHaveBeenCalled();
        done();
      }, 10);
    });

    it('returns cleanup function', () => {
      const cleanup = detectSwipe(element, {}, 50);
      expect(typeof cleanup).toBe('function');
      cleanup();
    });
  });

  describe('detectLongPress', () => {
    it('detects long press', (done) => {
      const callback = vi.fn();

      detectLongPress(element, callback, 100);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 50 }],
      });

      element.dispatchEvent(touchStartEvent);

      setTimeout(() => {
        expect(callback).toHaveBeenCalled();
        done();
      }, 150);
    });

    it('cancels on touchend before duration', (done) => {
      const callback = vi.fn();

      detectLongPress(element, callback, 200);

      const touchStartEvent = new TouchEvent('touchstart', {
        touches: [{ clientX: 50, clientY: 50 }],
      });
      const touchEndEvent = new TouchEvent('touchend', {
        touches: [],
      });

      element.dispatchEvent(touchStartEvent);

      setTimeout(() => {
        element.dispatchEvent(touchEndEvent);
      }, 100);

      setTimeout(() => {
        expect(callback).not.toHaveBeenCalled();
        done();
      }, 250);
    });

    it('returns cleanup function', () => {
      const cleanup = detectLongPress(element, () => {}, 500);
      expect(typeof cleanup).toBe('function');
      cleanup();
    });
  });

  describe('useSwipe Hook', () => {
    it('returns event handlers', () => {
      const callbacks = {
        onSwipeLeft: vi.fn(),
      };

      const handlers = useSwipe(callbacks, 50);

      expect(handlers).toHaveProperty('onTouchStart');
      expect(handlers).toHaveProperty('onTouchEnd');
      expect(typeof handlers.onTouchStart).toBe('function');
      expect(typeof handlers.onTouchEnd).toBe('function');
    });
  });

  describe('useLongPress Hook', () => {
    it('returns event handlers', () => {
      const callback = vi.fn();
      const handlers = useLongPress(callback, 500);

      expect(handlers).toHaveProperty('onTouchStart');
      expect(handlers).toHaveProperty('onTouchEnd');
      expect(handlers).toHaveProperty('onTouchMove');
      expect(typeof handlers.onTouchStart).toBe('function');
      expect(typeof handlers.onTouchEnd).toBe('function');
      expect(typeof handlers.onTouchMove).toBe('function');
    });
  });
});
