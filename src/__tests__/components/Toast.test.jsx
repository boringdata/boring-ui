import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Toast from '../../components/Toast';
import { ToastProvider, useToast } from '../../context/ToastContext';

describe('Toast Component', () => {
  it('renders toast with title and message', () => {
    render(
      <Toast
        id="1"
        type="info"
        title="Test Title"
        message="Test Message"
        onClose={() => {}}
      />
    );
    expect(screen.getByText('Test Title')).toBeInTheDocument();
    expect(screen.getByText('Test Message')).toBeInTheDocument();
  });

  it('renders toast with different types', () => {
    const types = ['success', 'error', 'warning', 'info'];
    types.forEach(type => {
      const { container } = render(
        <Toast
          id="1"
          type={type}
          title="Test"
          onClose={() => {}}
        />
      );
      expect(container.querySelector('[role="alert"]')).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByLabelText('Dismiss notification'));
    expect(onClose).toHaveBeenCalledWith('1');
  });

  it('auto-dismisses after duration', async () => {
    const onClose = vi.fn();
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        duration={100}
        onClose={onClose}
      />
    );

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledWith('1');
    }, { timeout: 200 });
  });

  it('renders action button when provided', () => {
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        action={{ label: 'Undo', onClick: vi.fn() }}
        onClose={() => {}}
      />
    );
    expect(screen.getByText('Undo')).toBeInTheDocument();
  });

  it('calls action onClick when button is clicked', () => {
    const actionClick = vi.fn();
    const onClose = vi.fn();
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        action={{ label: 'Undo', onClick: actionClick }}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByText('Undo'));
    expect(actionClick).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('dismisses on Escape key when dismissible', () => {
    const onClose = vi.fn();
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        dismissible={true}
        onClose={onClose}
      />
    );

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledWith('1');
  });

  it('has proper accessibility attributes', () => {
    render(
      <Toast
        id="1"
        type="info"
        title="Test"
        onClose={() => {}}
      />
    );
    const toast = screen.getByRole('alert');
    expect(toast).toHaveAttribute('aria-live', 'polite');
    expect(toast).toHaveAttribute('aria-atomic', 'true');
  });
});

describe('ToastProvider and useToast', () => {
  const TestComponent = ({ onAction }) => {
    const toast = useToast();

    return (
      <div>
        <button onClick={() => onAction(toast)}>Trigger Toast</button>
      </div>
    );
  };

  it('throws error when useToast is used outside provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(
        <TestComponent onAction={() => {}} />
      );
    }).toThrow('useToast must be used within a ToastProvider');

    consoleError.mockRestore();
  });

  it('provides toast functions through useToast hook', () => {
    render(
      <ToastProvider>
        <TestComponent
          onAction={(toast) => {
            expect(typeof toast.success).toBe('function');
            expect(typeof toast.error).toBe('function');
            expect(typeof toast.warning).toBe('function');
            expect(typeof toast.info).toBe('function');
            expect(typeof toast.addToast).toBe('function');
            expect(typeof toast.removeToast).toBe('function');
            expect(typeof toast.clearToasts).toBe('function');
          }}
        />
      </ToastProvider>
    );
  });

  it('adds toast to queue', async () => {
    const AddToastComponent = () => {
      const toast = useToast();

      return (
        <button onClick={() => toast.success('Success', 'Action completed')}>
          Add Toast
        </button>
      );
    };

    render(
      <ToastProvider>
        <AddToastComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Add Toast'));

    // Wait for toast to appear
    await waitFor(() => {
      expect(screen.getByText('Success')).toBeInTheDocument();
    });
  });

  it('maintains max toast limit', async () => {
    const AddToastsComponent = () => {
      const toast = useToast();

      return (
        <button
          onClick={() => {
            for (let i = 0; i < 5; i++) {
              toast.info(`Info ${i}`, `Message ${i}`);
            }
          }}
        >
          Add Multiple Toasts
        </button>
      );
    };

    render(
      <ToastProvider maxToasts={3}>
        <AddToastsComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Add Multiple Toasts'));

    await waitFor(() => {
      // Only 3 toasts should be visible
      const alerts = screen.getAllByRole('alert');
      expect(alerts.length).toBeLessThanOrEqual(3);
    });
  });

  it('removes toast when requested', async () => {
    const RemoveToastComponent = () => {
      const toast = useToast();
      const [toastId, setToastId] = React.useState(null);

      return (
        <div>
          <button
            onClick={() => {
              const id = toast.info('Info', 'Message');
              setToastId(id);
            }}
          >
            Add Toast
          </button>
          {toastId && (
            <button onClick={() => toast.removeToast(toastId)}>
              Remove Toast
            </button>
          )}
        </div>
      );
    };

    render(
      <ToastProvider>
        <RemoveToastComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Add Toast'));

    await waitFor(() => {
      expect(screen.getByText('Info')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Remove Toast'));

    await waitFor(() => {
      expect(screen.queryByText('Info')).not.toBeInTheDocument();
    });
  });

  it('clears all toasts', async () => {
    const ClearToastsComponent = () => {
      const toast = useToast();

      return (
        <div>
          <button
            onClick={() => {
              toast.info('Info 1', 'Message 1', { duration: false });
              toast.info('Info 2', 'Message 2', { duration: false });
            }}
          >
            Add Toasts
          </button>
          <button onClick={() => toast.clearToasts()}>
            Clear All
          </button>
        </div>
      );
    };

    render(
      <ToastProvider>
        <ClearToastsComponent />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText('Add Toasts'));

    await waitFor(() => {
      expect(screen.getByText('Info 1')).toBeInTheDocument();
      expect(screen.getByText('Info 2')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Clear All'));

    await waitFor(() => {
      expect(screen.queryByText('Info 1')).not.toBeInTheDocument();
      expect(screen.queryByText('Info 2')).not.toBeInTheDocument();
    });
  });

  it('provides convenience methods', async () => {
    const TestComponent = () => {
      const toast = useToast();

      return (
        <div>
          <button onClick={() => toast.success('Success', 'Message')}>Success</button>
          <button onClick={() => toast.error('Error', 'Message')}>Error</button>
          <button onClick={() => toast.warning('Warning', 'Message')}>Warning</button>
          <button onClick={() => toast.info('Info', 'Message')}>Info</button>
        </div>
      );
    };

    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]); // Success

    await waitFor(() => {
      expect(screen.getByText('Success')).toBeInTheDocument();
    });
  });
});
