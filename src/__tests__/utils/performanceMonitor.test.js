import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  measureOperation,
  getAverageDuration,
  getMetrics,
  trackWebVitals,
  getMemoryUsage,
  getResourceTimings,
  getNavigationTiming,
  clearMetrics,
  checkPerformanceBudget,
} from '../../utils/performanceMonitor'

/**
 * STORY-C012: Performance Optimization & Analytics
 * Test suite for performance monitoring utilities
 */

describe('Performance Monitor', () => {
  beforeEach(() => {
    clearMetrics()
  })

  describe('measureOperation', () => {
    it('measures operation duration', async () => {
      const result = await measureOperation('test-op', async () => {
        await new Promise((resolve) => setTimeout(resolve, 10))
        return 'result'
      })

      expect(result).toBe('result')
      expect(getAverageDuration('test-op')).toBeGreaterThanOrEqual(10)
    })

    it('stores multiple measurements', async () => {
      for (let i = 0; i < 3; i++) {
        await measureOperation('multi-op', async () => {
          await new Promise((resolve) => setTimeout(resolve, 5))
        })
      }

      const metrics = getMetrics()
      expect(metrics.measures['multi-op'].count).toBe(3)
    })

    it('calculates average correctly', async () => {
      await measureOperation('avg-op', async () => {
        await new Promise((resolve) => setTimeout(resolve, 10))
      })

      await measureOperation('avg-op', async () => {
        await new Promise((resolve) => setTimeout(resolve, 20))
      })

      const avg = getAverageDuration('avg-op')
      expect(avg).toBeGreaterThan(10)
      expect(avg).toBeLessThan(30)
    })

    it('handles errors gracefully', async () => {
      const errorOp = measureOperation('error-op', async () => {
        throw new Error('Test error')
      })

      await expect(errorOp).rejects.toThrow('Test error')
    })

    it('warns when exceeding threshold', async () => {
      const warnSpy = vi.spyOn(console, 'warn')

      await measureOperation('message-render', async () => {
        await new Promise((resolve) => setTimeout(resolve, 150))
      })

      expect(warnSpy).toHaveBeenCalled()
      warnSpy.mockRestore()
    })
  })

  describe('getMetrics', () => {
    it('returns empty metrics initially', () => {
      const metrics = getMetrics()
      expect(metrics).toEqual({ measures: {} })
    })

    it('includes all measured operations', async () => {
      await measureOperation('op1', async () => {})
      await measureOperation('op2', async () => {})

      const metrics = getMetrics()
      expect(metrics.measures).toHaveProperty('op1')
      expect(metrics.measures).toHaveProperty('op2')
    })

    it('calculates min, max, average for each operation', async () => {
      for (let i = 0; i < 5; i++) {
        await measureOperation('range-op', async () => {
          await new Promise((resolve) => setTimeout(resolve, 10 + i * 5))
        })
      }

      const metrics = getMetrics()
      const rangeMetric = metrics.measures['range-op']

      expect(rangeMetric.average).toBeGreaterThan(0)
      expect(rangeMetric.min).toBeLessThanOrEqual(rangeMetric.average)
      expect(rangeMetric.max).toBeGreaterThanOrEqual(rangeMetric.average)
      expect(rangeMetric.count).toBe(5)
    })
  })

  describe('getAverageDuration', () => {
    it('returns 0 for non-existent operation', () => {
      expect(getAverageDuration('non-existent')).toBe(0)
    })

    it('returns average of measurements', async () => {
      await measureOperation('test', async () => {})
      await measureOperation('test', async () => {})

      const avg = getAverageDuration('test')
      expect(avg).toBeGreaterThanOrEqual(0)
    })
  })

  describe('clearMetrics', () => {
    it('clears all metrics', async () => {
      await measureOperation('op1', async () => {})
      await measureOperation('op2', async () => {})

      clearMetrics()

      expect(getAverageDuration('op1')).toBe(0)
      expect(getAverageDuration('op2')).toBe(0)
    })
  })

  describe('checkPerformanceBudget', () => {
    it('passes when all metrics within budget', async () => {
      await measureOperation('message-render', async () => {
        await new Promise((resolve) => setTimeout(resolve, 50))
      })

      const result = checkPerformanceBudget()
      expect(result.passed).toBe(true)
      expect(result.violations).toHaveLength(0)
    })

    it('fails when exceeding budget', async () => {
      await measureOperation('message-render', async () => {
        await new Promise((resolve) => setTimeout(resolve, 150))
      })

      const result = checkPerformanceBudget()
      expect(result.passed).toBe(false)
      expect(result.violations.length).toBeGreaterThan(0)
    })

    it('includes violation details', async () => {
      await measureOperation('code-highlight', async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
      })

      const result = checkPerformanceBudget()
      if (!result.passed) {
        const violation = result.violations[0]
        expect(violation).toHaveProperty('metric')
        expect(violation).toHaveProperty('budget')
        expect(violation).toHaveProperty('actual')
        expect(violation).toHaveProperty('over')
      }
    })
  })

  describe('trackWebVitals', () => {
    it('sets up web vitals tracking', () => {
      const callback = vi.fn()
      const untrack = trackWebVitals(callback)

      expect(typeof untrack).toBe('function')
    })

    it('handles missing PerformanceObserver gracefully', () => {
      const originalObserver = global.PerformanceObserver
      delete global.PerformanceObserver

      const callback = vi.fn()
      trackWebVitals(callback)

      global.PerformanceObserver = originalObserver
      expect(callback).not.toHaveBeenCalled()
    })
  })

  describe('getMemoryUsage', () => {
    it('returns null when memory API not available', () => {
      const originalMemory = performance.memory
      delete performance.memory

      const usage = getMemoryUsage()
      expect(usage).toBeNull()

      performance.memory = originalMemory
    })

    it('returns memory metrics when available', () => {
      if (performance.memory) {
        const usage = getMemoryUsage()
        expect(usage).toHaveProperty('usedJSHeapSize')
        expect(usage).toHaveProperty('totalJSHeapSize')
        expect(usage).toHaveProperty('jsHeapSizeLimit')
      }
    })
  })

  describe('getResourceTimings', () => {
    it('returns resource timing data', () => {
      const timings = getResourceTimings()

      expect(timings).toHaveProperty('total')
      expect(timings).toHaveProperty('byType')
      expect(timings).toHaveProperty('totalTime')
      expect(timings).toHaveProperty('largestResources')
    })

    it('provides resource type breakdown', () => {
      const timings = getResourceTimings()
      expect(typeof timings.byType).toBe('object')
    })
  })

  describe('getNavigationTiming', () => {
    it('returns navigation timing data', () => {
      const timing = getNavigationTiming()

      if (timing) {
        expect(timing).toHaveProperty('DNS')
        expect(timing).toHaveProperty('TCP')
        expect(timing).toHaveProperty('Request')
        expect(timing).toHaveProperty('Response')
        expect(timing).toHaveProperty('DOM')
        expect(timing).toHaveProperty('Load')
        expect(timing).toHaveProperty('Total')
      }
    })
  })
})

describe('Performance Thresholds', () => {
  afterEach(() => {
    clearMetrics()
  })

  it('message-render should be <100ms', async () => {
    await measureOperation('message-render', async () => {
      await new Promise((resolve) => setTimeout(resolve, 80))
    })

    const result = checkPerformanceBudget()
    const violation = result.violations.find((v) => v.metric.includes('Message'))

    expect(violation).toBeUndefined()
  })

  it('code-highlight should be <50ms', async () => {
    await measureOperation('code-highlight', async () => {
      await new Promise((resolve) => setTimeout(resolve, 40))
    })

    const result = checkPerformanceBudget()
    const violation = result.violations.find((v) => v.metric.includes('Code'))

    expect(violation).toBeUndefined()
  })

  it('search should be <200ms', async () => {
    await measureOperation('search', async () => {
      await new Promise((resolve) => setTimeout(resolve, 150))
    })

    const result = checkPerformanceBudget()
    const violation = result.violations.find((v) => v.metric.includes('Search'))

    expect(violation).toBeUndefined()
  })

  it('action should be <100ms', async () => {
    await measureOperation('action', async () => {
      await new Promise((resolve) => setTimeout(resolve, 80))
    })

    const result = checkPerformanceBudget()
    const violation = result.violations.find((v) => v.metric.includes('Action'))

    expect(violation).toBeUndefined()
  })
})
