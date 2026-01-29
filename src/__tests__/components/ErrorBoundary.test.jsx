import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ErrorBoundary from '../../components/ErrorBoundary';

// Component that throws an error
const ThrowError = ({ shouldThrow = false, error = new Error('Test error') }) => {
  if (shouldThrow) {
    throw error;
  }
  return <div>No error</div>;
};

// Suppress console.error for error boundary tests
const originalError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalError;
});

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test Content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('displays error fallback UI when error is thrown', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('displays custom title and message', () => {
    render(
      <ErrorBoundary title="Custom Error" message="Custom message">
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom Error')).toBeInTheDocument();
    expect(screen.getByText('Custom message')).toBeInTheDocument();
  });

  it('has try again button', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('calls onError callback when error occurs', () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(onError).toHaveBeenCalled();
  });

  it('calls onReset callback when try again is clicked', () => {
    const onReset = vi.fn();
    render(
      <ErrorBoundary onReset={onReset}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    fireEvent.click(screen.getByText('Try Again'));
    expect(onReset).toHaveBeenCalled();
  });

  it('shows contact support button when onContactSupport is provided', () => {
    const onContactSupport = vi.fn();
    render(
      <ErrorBoundary onContactSupport={onContactSupport}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    const supportButton = screen.getByText('Contact Support');
    expect(supportButton).toBeInTheDocument();
  });

  it('calls onContactSupport when button is clicked', () => {
    const onContactSupport = vi.fn();
    render(
      <ErrorBoundary onContactSupport={onContactSupport}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    fireEvent.click(screen.getByText('Contact Support'));
    expect(onContactSupport).toHaveBeenCalled();
  });

  it('shows dismiss button when dismissible is true', () => {
    render(
      <ErrorBoundary dismissible={true}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    const dismissButton = screen.getByLabelText('Dismiss error');
    expect(dismissButton).toBeInTheDocument();
  });

  it('hides error when dismiss button is clicked', () => {
    render(
      <ErrorBoundary dismissible={true}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    const dismissButton = screen.getByLabelText('Dismiss error');
    fireEvent.click(dismissButton);
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('shows error details in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} error={new Error('Test error message')} />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Show Details/)).toBeInTheDocument();

    // Click to show details
    fireEvent.click(screen.getByText(/Show Details/));
    expect(screen.getByText('Test error message')).toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  it('toggles details visibility', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const toggleButton = screen.getByText(/Show Details/);
    expect(toggleButton).toBeInTheDocument();

    // Initially collapsed - should not show component stack
    expect(screen.queryByText('Component Stack:')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(toggleButton);
    expect(screen.getByText('Component Stack:')).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText(/Hide Details/));
    expect(screen.queryByText('Component Stack:')).not.toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  it('has proper accessibility attributes', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
  });
});
