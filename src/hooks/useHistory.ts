import { useState, useCallback } from 'react';
import type { UseHistoryReturn } from '../types';

/**
 * useHistory Hook
 * Manages undo/redo history for any state
 *
 * @param {T} initialValue - Initial history value
 * @returns {UseHistoryReturn<T>} History API
 *
 * @example
 * ```tsx
 * const history = useHistory<string>('initial value');
 *
 * history.push('new value');
 * history.undo(); // back to 'initial value'
 * history.redo(); // back to 'new value'
 * ```
 */
export function useHistory<T>(initialValue: T): UseHistoryReturn<T> {
  const [history, setHistory] = useState<T[]>([initialValue]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const canUndo = currentIndex > 0;
  const canRedo = currentIndex < history.length - 1;

  const undo = useCallback(() => {
    if (canUndo) {
      setCurrentIndex(prev => prev - 1);
    }
  }, [canUndo]);

  const redo = useCallback(() => {
    if (canRedo) {
      setCurrentIndex(prev => prev + 1);
    }
  }, [canRedo]);

  const push = useCallback((value: T) => {
    // Remove any history after current index
    const newHistory = history.slice(0, currentIndex + 1);
    newHistory.push(value);
    setHistory(newHistory);
    setCurrentIndex(newHistory.length - 1);
  }, [history, currentIndex]);

  const reset = useCallback(() => {
    setHistory([initialValue]);
    setCurrentIndex(0);
  }, [initialValue]);

  return {
    history,
    currentIndex,
    canUndo,
    canRedo,
    undo,
    redo,
    push,
    reset,
  };
}

export default useHistory;
