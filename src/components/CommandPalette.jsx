import React, { useState, useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { Search, Command, X } from 'lucide-react';
import { useKeyboardEvent } from '../hooks/useKeyboardShortcuts';

/**
 * CommandPalette Component
 * Quick command palette with keyboard shortcuts and fuzzy search
 *
 * @component
 * @example
 * ```jsx
 * <CommandPalette
 *   commands={[
 *     { id: 'save', label: 'Save', action: () => save() },
 *     { id: 'search', label: 'Search', action: () => search() }
 *   ]}
 * />
 * ```
 */
const CommandPalette = React.forwardRef(({
  commands = [],
  onSearch,
  onClose,
  placeholder = 'Search commands...',
  hotkey = 'k',
  className,
  ...props
}, ref) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  // Open palette with Cmd+K
  useKeyboardEvent(hotkey, () => {
    setIsOpen(true);
    setQuery('');
  }, { ctrl: true });

  // Close on Escape
  useKeyboardEvent('Escape', () => {
    if (isOpen) {
      setIsOpen(false);
    }
  });

  // Filter commands based on query
  const filteredCommands = query
    ? commands.filter(cmd =>
        cmd.label.toLowerCase().includes(query.toLowerCase()) ||
        cmd.id.toLowerCase().includes(query.toLowerCase())
      )
    : commands;

  // Handle command selection
  const handleSelect = (command) => {
    command.action?.();
    setIsOpen(false);
    setQuery('');
    onClose?.();
  };

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev =>
            prev < filteredCommands.length - 1 ? prev + 1 : 0
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev =>
            prev > 0 ? prev - 1 : filteredCommands.length - 1
          );
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            handleSelect(filteredCommands[selectedIndex]);
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex]);

  // Auto-focus input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={() => setIsOpen(false)}
      />

      {/* Command Palette */}
      <div
        ref={ref}
        className={clsx(
          'fixed inset-0 z-50 flex items-start justify-center pt-[20vh] pointer-events-none',
          className
        )}
        {...props}
      >
        <div
          ref={containerRef}
          className="w-full max-w-md pointer-events-auto"
        >
          {/* Input */}
          <div className="bg-background border rounded-lg shadow-lg overflow-hidden">
            <div className="flex items-center border-b px-4 py-3 gap-3">
              <Search size={20} className="text-foreground/50" />
              <input
                ref={inputRef}
                type="text"
                placeholder={placeholder}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSelectedIndex(0);
                  onSearch?.(e.target.value);
                }}
                className="flex-1 bg-transparent outline-none text-foreground placeholder:text-foreground/50"
              />
              {isOpen && (
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-foreground/10 rounded transition-colors"
                  aria-label="Close command palette"
                >
                  <X size={16} className="text-foreground/50" />
                </button>
              )}
            </div>

            {/* Commands List */}
            <div className="max-h-[400px] overflow-y-auto">
              {filteredCommands.length > 0 ? (
                filteredCommands.map((command, index) => (
                  <button
                    key={command.id}
                    onClick={() => handleSelect(command)}
                    className={clsx(
                      'w-full px-4 py-3 text-left flex items-center justify-between gap-3',
                      'hover:bg-foreground/10 transition-colors',
                      index === selectedIndex && 'bg-foreground/10',
                      'border-b last:border-b-0'
                    )}
                    role="option"
                    aria-selected={index === selectedIndex}
                  >
                    <span className="text-foreground">
                      {command.label}
                    </span>
                    {command.shortcut && (
                      <span className="text-xs text-foreground/50 font-mono">
                        {command.shortcut}
                      </span>
                    )}
                  </button>
                ))
              ) : (
                <div className="px-4 py-8 text-center text-foreground/50">
                  No commands found
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 bg-foreground/5 border-t text-xs text-foreground/50 flex gap-4">
              <div className="flex items-center gap-1">
                <Command size={14} />
                <span>↑↓</span>
                <span>Navigate</span>
              </div>
              <div className="flex items-center gap-1">
                <span>↵</span>
                <span>Select</span>
              </div>
              <div className="flex items-center gap-1">
                <span>Esc</span>
                <span>Close</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
});

CommandPalette.displayName = 'CommandPalette';

export default CommandPalette;
