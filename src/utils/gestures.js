/**
 * Touch Gesture Utilities
 * Support for swipe, long-press, pinch, and other touch gestures
 */

/**
 * Detect swipe gesture
 * @param {HTMLElement} element - Element to listen on
 * @param {Object} callbacks - Gesture callbacks
 * @param {Function} callbacks.onSwipeLeft - Left swipe callback
 * @param {Function} callbacks.onSwipeRight - Right swipe callback
 * @param {Function} callbacks.onSwipeUp - Up swipe callback
 * @param {Function} callbacks.onSwipeDown - Down swipe callback
 * @param {number} threshold - Minimum distance for swipe (default: 50px)
 * @returns {Function} Cleanup function
 */
export function detectSwipe(element, callbacks = {}, threshold = 50) {
  let touchStartX = 0;
  let touchStartY = 0;

  const handleTouchStart = (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  };

  const handleTouchEnd = (e) => {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;

    const diffX = touchStartX - touchEndX;
    const diffY = touchStartY - touchEndY;

    // Check horizontal swipe
    if (Math.abs(diffX) > threshold && Math.abs(diffX) > Math.abs(diffY)) {
      if (diffX > 0) {
        callbacks.onSwipeLeft?.();
      } else {
        callbacks.onSwipeRight?.();
      }
    }

    // Check vertical swipe
    if (Math.abs(diffY) > threshold && Math.abs(diffY) > Math.abs(diffX)) {
      if (diffY > 0) {
        callbacks.onSwipeUp?.();
      } else {
        callbacks.onSwipeDown?.();
      }
    }
  };

  element.addEventListener('touchstart', handleTouchStart);
  element.addEventListener('touchend', handleTouchEnd);

  return () => {
    element.removeEventListener('touchstart', handleTouchStart);
    element.removeEventListener('touchend', handleTouchEnd);
  };
}

/**
 * Detect long-press gesture
 * @param {HTMLElement} element - Element to listen on
 * @param {Function} callback - Long-press callback
 * @param {number} duration - Duration in ms (default: 500ms)
 * @returns {Function} Cleanup function
 */
export function detectLongPress(element, callback, duration = 500) {
  let timeoutId;
  let isLongPress = false;

  const handleTouchStart = () => {
    isLongPress = false;
    timeoutId = setTimeout(() => {
      isLongPress = true;
      callback();
    }, duration);
  };

  const handleTouchEnd = () => {
    clearTimeout(timeoutId);
  };

  const handleTouchMove = () => {
    if (isLongPress) {
      clearTimeout(timeoutId);
    }
  };

  element.addEventListener('touchstart', handleTouchStart);
  element.addEventListener('touchend', handleTouchEnd);
  element.addEventListener('touchmove', handleTouchMove);

  return () => {
    element.removeEventListener('touchstart', handleTouchStart);
    element.removeEventListener('touchend', handleTouchEnd);
    element.removeEventListener('touchmove', handleTouchMove);
  };
}

/**
 * Detect pinch-zoom gesture
 * @param {HTMLElement} element - Element to listen on
 * @param {Object} callbacks - Gesture callbacks
 * @param {Function} callbacks.onPinchStart - Pinch start callback
 * @param {Function} callbacks.onPinch - Pinch callback with scale
 * @param {Function} callbacks.onPinchEnd - Pinch end callback
 * @returns {Function} Cleanup function
 */
export function detectPinch(element, callbacks = {}) {
  let initialDistance = 0;

  const getDistance = (touches) => {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  };

  const handleTouchStart = (e) => {
    if (e.touches.length === 2) {
      initialDistance = getDistance(e.touches);
      callbacks.onPinchStart?.();
    }
  };

  const handleTouchMove = (e) => {
    if (e.touches.length === 2) {
      const currentDistance = getDistance(e.touches);
      const scale = currentDistance / initialDistance;
      callbacks.onPinch?.(scale);
    }
  };

  const handleTouchEnd = () => {
    callbacks.onPinchEnd?.();
  };

  element.addEventListener('touchstart', handleTouchStart);
  element.addEventListener('touchmove', handleTouchMove);
  element.addEventListener('touchend', handleTouchEnd);

  return () => {
    element.removeEventListener('touchstart', handleTouchStart);
    element.removeEventListener('touchmove', handleTouchMove);
    element.removeEventListener('touchend', handleTouchEnd);
  };
}

/**
 * useSwipe Hook
 * React hook for swipe detection
 * @param {Object} callbacks - Gesture callbacks
 * @param {number} threshold - Minimum distance for swipe
 * @returns {Object} Event handler to attach to element
 */
export function useSwipe(callbacks = {}, threshold = 50) {
  return {
    onTouchStart: (e) => {
      const touch = e.touches[0];
      e.currentTarget._swipeStart = { x: touch.clientX, y: touch.clientY };
    },
    onTouchEnd: (e) => {
      const start = e.currentTarget._swipeStart;
      if (!start) return;

      const end = { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY };
      const diffX = start.x - end.x;
      const diffY = start.y - end.y;

      if (Math.abs(diffX) > threshold && Math.abs(diffX) > Math.abs(diffY)) {
        if (diffX > 0) {
          callbacks.onSwipeLeft?.();
        } else {
          callbacks.onSwipeRight?.();
        }
      }

      if (Math.abs(diffY) > threshold && Math.abs(diffY) > Math.abs(diffX)) {
        if (diffY > 0) {
          callbacks.onSwipeUp?.();
        } else {
          callbacks.onSwipeDown?.();
        }
      }
    },
  };
}

/**
 * useLongPress Hook
 * React hook for long-press detection
 * @param {Function} callback - Long-press callback
 * @param {number} duration - Duration in ms
 * @returns {Object} Event handlers to attach to element
 */
export function useLongPress(callback, duration = 500) {
  const timeoutRef = { id: null, isLongPress: false };

  return {
    onTouchStart: () => {
      timeoutRef.isLongPress = false;
      timeoutRef.id = setTimeout(() => {
        timeoutRef.isLongPress = true;
        callback();
      }, duration);
    },
    onTouchEnd: () => {
      clearTimeout(timeoutRef.id);
    },
    onTouchMove: () => {
      if (timeoutRef.isLongPress) {
        clearTimeout(timeoutRef.id);
      }
    },
  };
}

/**
 * usePinch Hook
 * React hook for pinch-zoom detection
 * @param {Object} callbacks - Gesture callbacks
 * @returns {Object} Event handlers to attach to element
 */
export function usePinch(callbacks = {}) {
  const pinchRef = { initialDistance: 0 };

  const getDistance = (touches) => {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  };

  return {
    onTouchStart: (e) => {
      if (e.touches.length === 2) {
        pinchRef.initialDistance = getDistance(e.touches);
        callbacks.onPinchStart?.();
      }
    },
    onTouchMove: (e) => {
      if (e.touches.length === 2) {
        const currentDistance = getDistance(e.touches);
        const scale = currentDistance / pinchRef.initialDistance;
        callbacks.onPinch?.(scale);
      }
    },
    onTouchEnd: () => {
      callbacks.onPinchEnd?.();
    },
  };
}

/**
 * Haptic feedback (vibration)
 * @param {number} duration - Duration in ms (default: 50ms)
 */
export function vibrate(duration = 50) {
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    navigator.vibrate(duration);
  }
}

/**
 * Multi-tap detection
 * @param {HTMLElement} element - Element to listen on
 * @param {Function} callback - Callback when tapped N times
 * @param {number} tapCount - Number of taps (default: 2)
 * @param {number} timeout - Timeout between taps in ms (default: 300ms)
 * @returns {Function} Cleanup function
 */
export function detectMultiTap(element, callback, tapCount = 2, timeout = 300) {
  let taps = 0;
  let timeoutId;

  const handleTap = () => {
    taps++;

    if (taps === tapCount) {
      callback();
      taps = 0;
      clearTimeout(timeoutId);
    } else {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        taps = 0;
      }, timeout);
    }
  };

  element.addEventListener('touchend', handleTap);

  return () => {
    element.removeEventListener('touchend', handleTap);
    clearTimeout(timeoutId);
  };
}

export default {
  detectSwipe,
  detectLongPress,
  detectPinch,
  detectMultiTap,
  vibrate,
  useSwipe,
  useLongPress,
  usePinch,
};
