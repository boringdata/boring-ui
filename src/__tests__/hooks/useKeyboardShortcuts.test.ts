import { describe, it, expect, vi } from 'vitest';
import { getKeyCombo, parseKeyCombo } from '../../hooks/useKeyboardShortcuts';

describe('useKeyboardShortcuts Utilities', () => {
  describe('getKeyCombo', () => {
    it('converts shortcut config to string', () => {
      const result = getKeyCombo({ key: 's', ctrl: true, callback: () => {} });
      expect(result).toBe('Ctrl+S');
    });

    it('handles multiple modifiers', () => {
      const result = getKeyCombo({
        key: 'k',
        ctrl: true,
        shift: true,
        callback: () => {},
      });
      expect(result).toBe('Ctrl+Shift+K');
    });

    it('handles meta key', () => {
      const result = getKeyCombo({
        key: 's',
        meta: true,
        callback: () => {},
      });
      expect(result).toBe('Cmd+S');
    });

    it('handles alt key', () => {
      const result = getKeyCombo({
        key: 'a',
        alt: true,
        callback: () => {},
      });
      expect(result).toBe('Alt+A');
    });

    it('converts key to uppercase', () => {
      const result = getKeyCombo({
        key: 'escape',
        callback: () => {},
      });
      expect(result).toBe('ESCAPE');
    });
  });

  describe('parseKeyCombo', () => {
    it('parses simple key combo', () => {
      const result = parseKeyCombo('Ctrl+S');
      expect(result).toEqual({ key: 's', ctrl: true, shift: false, alt: false, meta: false });
    });

    it('parses multiple modifiers', () => {
      const result = parseKeyCombo('Ctrl+Shift+K');
      expect(result).toEqual({
        key: 'k',
        ctrl: true,
        shift: true,
        alt: false,
        meta: false,
      });
    });

    it('parses meta key', () => {
      const result = parseKeyCombo('Cmd+S');
      expect(result.meta).toBe(true);
    });

    it('parses alt key', () => {
      const result = parseKeyCombo('Alt+A');
      expect(result.alt).toBe(true);
    });

    it('is case insensitive', () => {
      const result1 = parseKeyCombo('CTRL+S');
      const result2 = parseKeyCombo('ctrl+s');
      expect(result1).toEqual(result2);
    });

    it('handles single key', () => {
      const result = parseKeyCombo('Escape');
      expect(result.key).toBe('escape');
      expect(result.ctrl).toBe(false);
    });
  });

  describe('getKeyCombo and parseKeyCombo round-trip', () => {
    it('can round-trip shortcut config', () => {
      const original = {
        key: 'k',
        ctrl: true,
        shift: true,
        alt: false,
        meta: false,
      };

      const combo = getKeyCombo({ ...original, callback: () => {} });
      const parsed = parseKeyCombo(combo);

      expect(parsed).toEqual(original);
    });
  });
});
