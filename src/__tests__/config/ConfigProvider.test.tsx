import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from 'vitest';
import { render, screen } from '@testing-library/react';
// @ts-expect-error - JS module without types
import { ConfigProvider, useConfig } from '../../config';

// Component to test useConfig hook
function ConfigConsumer() {
  const config = useConfig();
  return <div data-testid="config">{JSON.stringify(config)}</div>;
}

describe('ConfigProvider', () => {
  let consoleErrorSpy: MockInstance;
  let consoleWarnSpy: MockInstance;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  describe('with valid config', () => {
    it('provides config to children', () => {
      render(
        <ConfigProvider config={{ branding: { name: 'Test App' } }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      const configEl = screen.getByTestId('config');
      const config = JSON.parse(configEl.textContent || '{}');
      expect(config.branding.name).toBe('Test App');
    });

    it('applies defaults for missing fields', () => {
      render(
        <ConfigProvider config={{}}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      const configEl = screen.getByTestId('config');
      const config = JSON.parse(configEl.textContent || '{}');
      // Should have default values
      expect(config.branding.name).toBe('My App');
      expect(config.features.gitStatus).toBe(true);
    });

    it('uses defaults when no config provided', () => {
      render(
        <ConfigProvider>
          <ConfigConsumer />
        </ConfigProvider>
      );

      const configEl = screen.getByTestId('config');
      const config = JSON.parse(configEl.textContent || '{}');
      expect(config.branding.name).toBe('My App');
    });
  });

  describe('with invalid config (failFast=true)', () => {
    it('shows error UI with invalid type', () => {
      render(
        <ConfigProvider config={{ fileTree: { gitPollInterval: 'not a number' } }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Should show error UI, not the config consumer
      expect(screen.getByText('Configuration Error')).toBeInTheDocument();
      expect(screen.queryByTestId('config')).not.toBeInTheDocument();
    });

    it('displays all validation errors (not just the first)', () => {
      render(
        <ConfigProvider config={{
          fileTree: {
            gitPollInterval: 'not a number',
            treePollInterval: 'also not a number',
          }
        }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Should show error count for multiple errors
      expect(screen.getByText(/Validation Errors \(2\)/)).toBeInTheDocument();
    });

    it('logs all errors to console', () => {
      render(
        <ConfigProvider config={{
          fileTree: {
            gitPollInterval: -1,  // Must be positive
            treePollInterval: -2, // Must be positive
          }
        }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Should have logged errors
      expect(consoleErrorSpy).toHaveBeenCalled();
      const errorCall = consoleErrorSpy.mock.calls[0][0];
      expect(errorCall).toContain('Configuration validation failed');
      expect(errorCall).toContain('fileTree.gitPollInterval');
      expect(errorCall).toContain('fileTree.treePollInterval');
    });

    it('logs the provided config for debugging', () => {
      const badConfig = { fileTree: { gitPollInterval: 'bad' } };
      render(
        <ConfigProvider config={badConfig}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Should log the config that was provided
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[ConfigProvider] Provided config:',
        badConfig
      );
    });
  });

  describe('with invalid config (failFast=false)', () => {
    it('falls back to defaults instead of showing error UI', () => {
      render(
        <ConfigProvider config={{ fileTree: { gitPollInterval: 'not a number' } }} failFast={false}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Should NOT show error UI
      expect(screen.queryByText('Configuration Error')).not.toBeInTheDocument();

      // Should render children with default config
      const configEl = screen.getByTestId('config');
      const config = JSON.parse(configEl.textContent || '{}');
      expect(config.branding.name).toBe('My App');
    });

    it('still logs errors when falling back', () => {
      render(
        <ConfigProvider config={{ fileTree: { gitPollInterval: 'not a number' } }} failFast={false}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      expect(consoleErrorSpy).toHaveBeenCalled();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '[ConfigProvider] Falling back to default configuration due to validation errors'
      );
    });
  });

  describe('error message formatting', () => {
    it('shows path for nested errors', () => {
      render(
        <ConfigProvider config={{ fileTree: { sections: [{ key: 123 }] } }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      // Error should reference the path
      const errorContent = screen.getByRole('heading', { name: /Configuration Error/ }).parentElement?.parentElement;
      expect(errorContent?.textContent).toContain('fileTree.sections');
    });

    it('includes expected type for type errors', () => {
      render(
        <ConfigProvider config={{ fileTree: { gitPollInterval: 'string' } }}>
          <ConfigConsumer />
        </ConfigProvider>
      );

      const errorCall = consoleErrorSpy.mock.calls[0][0];
      expect(errorCall).toContain('expected');
    });
  });
});
