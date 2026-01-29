import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useHistory } from '../../hooks/useHistory';

describe('useHistory Hook', () => {
  it('initializes with initial value', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));
    expect(result.current.history).toEqual(['initial']);
    expect(result.current.currentIndex).toBe(0);
  });

  it('pushes new value to history', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
    });

    expect(result.current.history).toEqual(['initial', 'second']);
    expect(result.current.currentIndex).toBe(1);
  });

  it('pushes multiple values', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
      result.current.push('third');
    });

    expect(result.current.history).toEqual(['initial', 'second', 'third']);
    expect(result.current.currentIndex).toBe(2);
  });

  it('undoes to previous value', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
      result.current.push('third');
    });

    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.currentIndex).toBe(1);
    expect(result.current.history[result.current.currentIndex]).toBe('second');
  });

  it('redoes to next value', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
      result.current.push('third');
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.redo();
    });

    expect(result.current.currentIndex).toBe(2);
    expect(result.current.history[result.current.currentIndex]).toBe('third');
  });

  it('cannot undo at start', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    expect(result.current.canUndo).toBe(false);

    act(() => {
      result.current.undo();
    });

    expect(result.current.currentIndex).toBe(0);
  });

  it('cannot redo at end', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
    });

    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.redo();
    });

    expect(result.current.currentIndex).toBe(1);
  });

  it('clears redo history when pushing after undo', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
      result.current.push('third');
      result.current.undo();
    });

    expect(result.current.history).toEqual(['initial', 'second', 'third']);

    act(() => {
      result.current.push('new');
    });

    expect(result.current.history).toEqual(['initial', 'second', 'new']);
    expect(result.current.canRedo).toBe(false);
  });

  it('resets to initial value', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
      result.current.push('third');
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.history).toEqual(['initial']);
    expect(result.current.currentIndex).toBe(0);
  });

  it('works with objects', () => {
    const initialObj = { value: 'initial' };
    const { result } = renderHook(() => useHistory(initialObj));

    act(() => {
      result.current.push({ value: 'updated' });
    });

    expect(result.current.history[0]).toEqual(initialObj);
    expect(result.current.history[1]).toEqual({ value: 'updated' });
  });

  it('works with numbers', () => {
    const { result } = renderHook(() => useHistory<number>(0));

    act(() => {
      result.current.push(1);
      result.current.push(2);
      result.current.push(3);
    });

    expect(result.current.history).toEqual([0, 1, 2, 3]);

    act(() => {
      result.current.undo();
      result.current.undo();
    });

    expect(result.current.currentIndex).toBe(1);
  });

  it('canUndo reflects correct state', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    expect(result.current.canUndo).toBe(false);

    act(() => {
      result.current.push('second');
    });

    expect(result.current.canUndo).toBe(true);

    act(() => {
      result.current.undo();
    });

    expect(result.current.canUndo).toBe(false);
  });

  it('canRedo reflects correct state', () => {
    const { result } = renderHook(() => useHistory<string>('initial'));

    act(() => {
      result.current.push('second');
    });

    expect(result.current.canRedo).toBe(false);

    act(() => {
      result.current.undo();
    });

    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.redo();
    });

    expect(result.current.canRedo).toBe(false);
  });
});
