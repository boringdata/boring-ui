/**
 * Performance Monitor Utility
 *
 * Tracks Web Vitals and performance metrics for the chat interface:
 * - Largest Contentful Paint (LCP): < 500ms
 * - First Input Delay (FID): < 100ms
 * - Cumulative Layout Shift (CLS): < 0.1
 * - Time to Interactive (TTI): < 1s
 * - Message render time: < 100ms
 * - Code highlight time: < 50ms
 * - Search response: < 200ms
 * - Action latency: < 100ms
 */

const performanceData = {
  metrics: {},
  marks: {},
  measures: {},
}

/**
 * Measure operation duration
 * @param {string} operationName - Name of operation
 * @param {Function} operation - Async operation to measure
 * @returns {Promise<any>} Operation result
 */
export async function measureOperation(operationName, operation) {
  const startMark = `${operationName}-start`
  const endMark = `${operationName}-end`
  const measureName = `${operationName}`

  try {
    performance.mark(startMark)

    const result = await operation()

    performance.mark(endMark)
    performance.measure(measureName, startMark, endMark)

    // Get the measure duration
    const measure = performance.getEntriesByName(measureName)[0]
    const duration = measure?.duration || 0

    // Store metric
    if (!performanceData.measures[measureName]) {
      performanceData.measures[measureName] = []
    }
    performanceData.measures[measureName].push(duration)

    // Warn if exceeds threshold
    const thresholds = {
      'message-render': 100,
      'code-highlight': 50,
      'search': 200,
      'action': 100,
      'api-call': 1000,
    }

    const threshold = Object.entries(thresholds).find(([key]) =>
      measureName.includes(key),
    )?.[1]

    if (threshold && duration > threshold) {
      console.warn(
        `Performance warning: ${measureName} took ${duration.toFixed(2)}ms (threshold: ${threshold}ms)`,
      )
    }

    return result
  } catch (error) {
    console.error(`Performance measurement error for ${operationName}:`, error)
    throw error
  }
}

/**
 * Get average duration for an operation
 * @param {string} operationName - Name of operation
 * @returns {number} Average duration in ms
 */
export function getAverageDuration(operationName) {
  const measures = performanceData.measures[operationName] || []
  if (measures.length === 0) return 0

  const sum = measures.reduce((acc, val) => acc + val, 0)
  return sum / measures.length
}

/**
 * Get all metrics collected
 * @returns {Object} Collected metrics
 */
export function getMetrics() {
  return {
    ...performanceData.metrics,
    measures: Object.entries(performanceData.measures).reduce(
      (acc, [key, values]) => ({
        ...acc,
        [key]: {
          average: getAverageDuration(key),
          min: Math.min(...values),
          max: Math.max(...values),
          count: values.length,
        },
      }),
      {},
    ),
  }
}

/**
 * Web Vitals tracking
 * Tracks LCP, FID, CLS
 */
export function trackWebVitals(callback) {
  const vitals = {}

  // Largest Contentful Paint
  if ('PerformanceObserver' in window) {
    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries()
        const lastEntry = entries[entries.length - 1]
        vitals.LCP = lastEntry.renderTime || lastEntry.loadTime

        if (callback) {
          callback({
            name: 'LCP',
            value: vitals.LCP,
            status: vitals.LCP < 500 ? 'good' : 'poor',
          })
        }
      })

      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] })

      // Cumulative Layout Shift
      const clsObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) {
            vitals.CLS = (vitals.CLS || 0) + entry.value

            if (callback) {
              callback({
                name: 'CLS',
                value: vitals.CLS,
                status: vitals.CLS < 0.1 ? 'good' : 'poor',
              })
            }
          }
        }
      })

      clsObserver.observe({ entryTypes: ['layout-shift'] })

      // First Input Delay
      const fidObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          vitals.FID = entry.processingDuration

          if (callback) {
            callback({
              name: 'FID',
              value: vitals.FID,
              status: vitals.FID < 100 ? 'good' : 'poor',
            })
          }
        }
      })

      fidObserver.observe({ entryTypes: ['first-input'] })

      return () => {
        lcpObserver.disconnect()
        clsObserver.disconnect()
        fidObserver.disconnect()
      }
    } catch (error) {
      console.error('Error tracking Web Vitals:', error)
    }
  }

  return () => {}
}

/**
 * Memory usage monitoring
 * Note: Only available in browsers with performance.memory
 */
export function getMemoryUsage() {
  if (performance.memory) {
    return {
      usedJSHeapSize: (performance.memory.usedJSHeapSize / 1048576).toFixed(2), // MB
      totalJSHeapSize: (performance.memory.totalJSHeapSize / 1048576).toFixed(2), // MB
      jsHeapSizeLimit: (performance.memory.jsHeapSizeLimit / 1048576).toFixed(2), // MB
    }
  }

  return null
}

/**
 * Resource timing analysis
 */
export function getResourceTimings() {
  const resources = performance.getEntriesByType('resource')

  return {
    total: resources.length,
    byType: resources.reduce(
      (acc, resource) => {
        const type = resource.initiatorType
        acc[type] = (acc[type] || 0) + 1
        return acc
      },
      {},
    ),
    totalTime: resources.reduce((acc, r) => acc + r.duration, 0),
    largestResources: resources
      .sort((a, b) => b.duration - a.duration)
      .slice(0, 5)
      .map((r) => ({
        name: r.name.split('/').pop(),
        duration: r.duration.toFixed(2),
        type: r.initiatorType,
      })),
  }
}

/**
 * Navigation timing analysis
 */
export function getNavigationTiming() {
  const navigation = performance.getEntriesByType('navigation')[0]

  if (!navigation) return null

  return {
    DNS: (navigation.domainLookupEnd - navigation.domainLookupStart).toFixed(2),
    TCP: (navigation.connectEnd - navigation.connectStart).toFixed(2),
    Request: (navigation.responseStart - navigation.requestStart).toFixed(2),
    Response: (navigation.responseEnd - navigation.responseStart).toFixed(2),
    DOM: (navigation.domContentLoadedEventEnd - navigation.responseEnd).toFixed(2),
    Load: (navigation.loadEventEnd - navigation.responseEnd).toFixed(2),
    Total: navigation.loadEventEnd.toFixed(2),
  }
}

/**
 * Clear all collected metrics
 */
export function clearMetrics() {
  performanceData.metrics = {}
  performanceData.marks = {}
  performanceData.measures = {}

  try {
    performance.clearMarks()
    performance.clearMeasures()
  } catch (e) {
    // Ignore errors from clearing
  }
}

/**
 * Report metrics to external service
 */
export function reportMetrics(endpoint) {
  if (!navigator.sendBeacon) {
    console.warn('sendBeacon not supported')
    return
  }

  const metrics = getMetrics()
  const memory = getMemoryUsage()
  const resources = getResourceTimings()
  const navigation = getNavigationTiming()

  const payload = JSON.stringify({
    timestamp: new Date().toISOString(),
    metrics,
    memory,
    resources,
    navigation,
    userAgent: navigator.userAgent,
  })

  try {
    navigator.sendBeacon(endpoint, payload)
  } catch (error) {
    console.error('Failed to report metrics:', error)
  }
}

/**
 * Performance budget checker
 */
export function checkPerformanceBudget() {
  const budgets = {
    'message-render': { threshold: 100, description: 'Message render time' },
    'code-highlight': { threshold: 50, description: 'Code highlighting' },
    'search': { threshold: 200, description: 'Search response' },
    'action': { threshold: 100, description: 'Action latency' },
  }

  const violations = []

  Object.entries(budgets).forEach(([key, { threshold, description }]) => {
    const avg = getAverageDuration(key)
    if (avg > threshold) {
      violations.push({
        metric: description,
        budget: threshold,
        actual: avg.toFixed(2),
        over: (avg - threshold).toFixed(2),
      })
    }
  })

  return {
    passed: violations.length === 0,
    violations,
  }
}

export default {
  measureOperation,
  getAverageDuration,
  getMetrics,
  trackWebVitals,
  getMemoryUsage,
  getResourceTimings,
  getNavigationTiming,
  clearMetrics,
  reportMetrics,
  checkPerformanceBudget,
}
