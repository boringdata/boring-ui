import { useEffect } from 'react';
import type { KeyboardShortcutConfig } from '../types';

/**
 * useKeyboardShortcuts Hook
 * Register keyboard shortcuts with modifier key support
 *
 * @param {KeyboardShortcutConfig[]} shortcuts - Array of shortcut configurations
 *
 * @example
 * ```tsx
 * useKeyboardShortcuts([
 *   {
 *     key: 's',
 *     ctrl: true,
 *     callback: () => saveDocument()
 *   },
 *   {
 *     key: 'k',
 *     ctrl: true,
 *     callback: () => openCommandPalette()
 *   }
 * ]);
 * ```
 */
export function useKeyboardShortcuts(shortcuts: KeyboardShortcutConfig[]): void {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      shortcuts.forEach(shortcut => {
        const {
          key,
          ctrl = false,
          shift = false,
          alt = false,
          meta = false,
          callback,
        } = shortcut;

        const keyMatches = event.key.toLowerCase() === key.toLowerCase();
        const ctrlMatches = ctrl === (event.ctrlKey || event.metaKey);
        const shiftMatches = shift === event.shiftKey;
        const altMatches = alt === event.altKey;
        const metaMatches = meta === event.metaKey;

        if (keyMatches && ctrlMatches && shiftMatches && altMatches && metaMatches) {
          event.preventDefault();
          callback(event);
        }
      });
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}

/**
 * useKeyboardEvent Hook
 * Listen for a specific keyboard event
 *
 * @param {string} key - The key to listen for
 * @param {Function} callback - Callback function
 * @param {Object} options - Modifier keys (ctrl, shift, alt, meta)
 *
 * @example
 * ```tsx
 * useKeyboardEvent('Escape', () => closeModal(), { ctrl: false });
 * ```
 */
export function useKeyboardEvent(
  key: string,
  callback: (event: KeyboardEvent) => void,
  options: {
    ctrl?: boolean;
    shift?: boolean;
    alt?: boolean;
    meta?: boolean;
  } = {}
): void {
  useKeyboardShortcuts([
    {
      key,
      ...options,
      callback,
    },
  ]);
}

/**
 * getKeyCombo Helper
 * Generate a human-readable keyboard shortcut string
 *
 * @param {KeyboardShortcutConfig} config - Shortcut configuration
 * @returns {string} Human-readable shortcut (e.g., "Ctrl+S")
 *
 * @example
 * ```tsx
 * getKeyCombo({ key: 's', ctrl: true }) // "Ctrl+S"
 * getKeyCombo({ key: 'k', ctrl: true, shift: true }) // "Ctrl+Shift+K"
 * ```
 */
export function getKeyCombo(config: KeyboardShortcutConfig): string {
  const keys: string[] = [];

  if (config.ctrl) keys.push('Ctrl');
  if (config.alt) keys.push('Alt');
  if (config.shift) keys.push('Shift');
  if (config.meta) keys.push('Cmd');

  keys.push(config.key.toUpperCase());

  return keys.join('+');
}

/**
 * parseKeyCombo Helper
 * Parse a keyboard shortcut string into configuration
 *
 * @param {string} combo - Keyboard combo string (e.g., "Ctrl+S")
 * @returns {Omit<KeyboardShortcutConfig, 'callback'>} Shortcut configuration
 *
 * @example
 * ```tsx
 * parseKeyCombo('Ctrl+S') // { key: 's', ctrl: true }
 * parseKeyCombo('Ctrl+Shift+K') // { key: 'k', ctrl: true, shift: true }
 * ```
 */
export function parseKeyCombo(
  combo: string
): Omit<KeyboardShortcutConfig, 'callback'> {
  const parts = combo.split('+').map(p => p.toLowerCase().trim());
  const lastPart = parts.pop() || '';

  return {
    key: lastPart,
    ctrl: parts.includes('ctrl'),
    shift: parts.includes('shift'),
    alt: parts.includes('alt'),
    meta: parts.includes('cmd') || parts.includes('meta'),
  };
}

export default useKeyboardShortcuts;
