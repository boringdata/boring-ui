import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  debounce,
  throttle,
  getCache,
  setCache,
  clearCache,
  isSlowDevice,
  measurePerformance,
} from '../../utils/performance';

describe('Performance Utilities', () => {
  describe('debounce', () => {
    it('delays function execution', (done) => {
      const fn = vi.fn();
      const debounced = debounce(fn, 100);

      debounced();
      debounced();
      debounced();

      expect(fn).not.toHaveBeenCalled();

      setTimeout(() => {
        expect(fn).toHaveBeenCalledTimes(1);
        done();
      }, 150);
    });

    it('resets timer on new calls', (done) => {
      const fn = vi.fn();
      const debounced = debounce(fn, 100);

      debounced();
      setTimeout(() => debounced(), 50);
      setTimeout(() => debounced(), 100);

      setTimeout(() => {
        expect(fn).toHaveBeenCalledTimes(1);
        done();
      }, 250);
    });

    it('passes arguments to function', (done) => {
      const fn = vi.fn();
      const debounced = debounce(fn, 50);

      debounced('test', 123);

      setTimeout(() => {
        expect(fn).toHaveBeenCalledWith('test', 123);
        done();
      }, 100);
    });
  });

  describe('throttle', () => {
    it('limits function execution rate', (done) => {
      const fn = vi.fn();
      const throttled = throttle(fn, 100);

      throttled();
      throttled();
      throttled();

      expect(fn).toHaveBeenCalledTimes(1);

      setTimeout(() => {
        throttled();
        expect(fn).toHaveBeenCalledTimes(2);
        done();
      }, 150);
    });

    it('executes function immediately', () => {
      const fn = vi.fn();
      const throttled = throttle(fn, 100);

      throttled();
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('waits for interval before next execution', (done) => {
      const fn = vi.fn();
      const throttled = throttle(fn, 100);

      throttled();
      throttled();

      setTimeout(() => {
        expect(fn).toHaveBeenCalledTimes(1);
      }, 50);

      setTimeout(() => {
        expect(fn).toHaveBeenCalledTimes(1);
        done();
      }, 100);
    });
  });

  describe('Cache', () => {
    beforeEach(() => {
      clearCache();
    });

    it('sets and gets cache value', () => {
      setCache('key', 'value');
      expect(getCache('key')).toBe('value');
    });

    it('returns null for missing key', () => {
      expect(getCache('nonexistent')).toBeNull();
    });

    it('expires cache values', (done) => {
      setCache('key', 'value', 100);
      expect(getCache('key')).toBe('value');

      setTimeout(() => {
        expect(getCache('key')).toBeNull();
        done();
      }, 150);
    });

    it('clears specific cache key', () => {
      setCache('key1', 'value1');
      setCache('key2', 'value2');

      clearCache('key1');

      expect(getCache('key1')).toBeNull();
      expect(getCache('key2')).toBe('value2');
    });

    it('clears all cache', () => {
      setCache('key1', 'value1');
      setCache('key2', 'value2');

      clearCache();

      expect(getCache('key1')).toBeNull();
      expect(getCache('key2')).toBeNull();
    });

    it('caches objects', () => {
      const obj = { name: 'test', value: 123 };
      setCache('obj', obj);
      expect(getCache('obj')).toEqual(obj);
    });

    it('caches arrays', () => {
      const arr = [1, 2, 3];
      setCache('arr', arr);
      expect(getCache('arr')).toEqual(arr);
    });
  });

  describe('isSlowDevice', () => {
    it('returns boolean', () => {
      const result = isSlowDevice();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('measurePerformance', () => {
    it('measures function execution time', () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation();

      const result = measurePerformance('test', () => {
        let sum = 0;
        for (let i = 0; i < 1000; i++) {
          sum += i;
        }
        return sum;
      });

      expect(result).toBeGreaterThan(0);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('returns callback result', () => {
      const result = measurePerformance('test', () => 'result value');
      expect(result).toBe('result value');
    });
  });
});
