/**
 * Debounce helper - delays function execution until after wait ms of inactivity.
 *
 * @param {Function} fn - Function to debounce
 * @param {number} wait - Milliseconds to wait
 * @returns {{ (...args: any[]): void, flush: () => void, cancel: () => void }}
 */
export const debounce = (fn, wait) => {
  let timeoutId = null
  const debounced = (...args) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      timeoutId = null
      fn(...args)
    }, wait)
  }
  // Allow immediate flush (for beforeunload)
  debounced.flush = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
      fn()
    }
  }
  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }
  return debounced
}
