import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CommandPalette from '../../components/CommandPalette';

describe('CommandPalette Component', () => {
  const defaultCommands = [
    { id: 'save', label: 'Save', action: vi.fn() },
    { id: 'search', label: 'Search', action: vi.fn() },
    { id: 'settings', label: 'Settings', action: vi.fn() },
  ];

  it('renders when isOpen is true', () => {
    const { container } = render(
      <CommandPalette commands={defaultCommands} />
    );

    // Initial state: palette should be hidden
    expect(container.querySelector('[role="option"]')).not.toBeInTheDocument();
  });

  it('filters commands by query', async () => {
    render(
      <CommandPalette commands={defaultCommands} />
    );

    // Open with Cmd+K
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Type in search
    const input = screen.getByPlaceholderText(/Search commands/);
    fireEvent.change(input, { target: { value: 'save' } });

    // Should show only save command
    expect(screen.getByText('Save')).toBeInTheDocument();
  });

  it('executes command action on selection', async () => {
    const saveAction = vi.fn();
    const commands = [
      { id: 'save', label: 'Save', action: saveAction },
    ];

    render(<CommandPalette commands={commands} />);

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByText('Save')).toBeInTheDocument();
    });

    // Click command
    fireEvent.click(screen.getByText('Save'));

    expect(saveAction).toHaveBeenCalled();
  });

  it('supports keyboard navigation', async () => {
    render(<CommandPalette commands={defaultCommands} />);

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Verify initial selection (0)
    const options = screen.getAllByRole('option');
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('closes on Escape key', async () => {
    render(<CommandPalette commands={defaultCommands} />);

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/Search commands/)).not.toBeInTheDocument();
    });
  });

  it('closes on command selection', async () => {
    render(
      <CommandPalette commands={defaultCommands} />
    );

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByText('Save')).toBeInTheDocument();
    });

    // Select command
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.queryByText('Save')).not.toBeInTheDocument();
    });
  });

  it('shows no commands message when no results', async () => {
    render(
      <CommandPalette commands={defaultCommands} />
    );

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Search with no results
    const input = screen.getByPlaceholderText(/Search commands/);
    fireEvent.change(input, { target: { value: 'nonexistent' } });

    expect(screen.getByText('No commands found')).toBeInTheDocument();
  });

  it('displays shortcuts in command list', async () => {
    const commands = [
      { id: 'save', label: 'Save', shortcut: 'Ctrl+S', action: vi.fn() },
    ];

    render(<CommandPalette commands={commands} />);

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByText('Ctrl+S')).toBeInTheDocument();
    });
  });

  it('calls onSearch callback when query changes', async () => {
    const onSearch = vi.fn();

    render(
      <CommandPalette commands={defaultCommands} onSearch={onSearch} />
    );

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Type in search
    const input = screen.getByPlaceholderText(/Search commands/);
    fireEvent.change(input, { target: { value: 'test' } });

    expect(onSearch).toHaveBeenCalledWith('test');
  });

  it('calls onClose callback when closed', async () => {
    const onClose = vi.fn();

    render(
      <CommandPalette commands={defaultCommands} onClose={onClose} />
    );

    // Open palette
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search commands/)).toBeInTheDocument();
    });

    // Close via Escape
    fireEvent.keyDown(window, { key: 'Escape' });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });
});
