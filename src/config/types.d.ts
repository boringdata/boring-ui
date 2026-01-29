import { z } from 'zod';
import {
  brandingSchema,
  fileTreeSectionSchema,
  fileTreeSchema,
  storageSchema,
  panelsSchema,
  apiSchema,
  featuresSchema,
  appConfigSchema,
} from './schema';

/** Branding configuration */
export type Branding = z.infer<typeof brandingSchema>;

/** FileTree section definition */
export type FileTreeSection = z.infer<typeof fileTreeSectionSchema>;

/** FileTree configuration */
export type FileTree = z.infer<typeof fileTreeSchema>;

/** Storage configuration */
export type Storage = z.infer<typeof storageSchema>;

/** Panels configuration */
export type Panels = z.infer<typeof panelsSchema>;

/** API configuration */
export type Api = z.infer<typeof apiSchema>;

/** Features configuration */
export type Features = z.infer<typeof featuresSchema>;

/** Complete application configuration */
export type AppConfig = z.infer<typeof appConfigSchema>;

/** Title format context passed to branding.titleFormat */
export interface TitleFormatContext {
  folder?: string;
  workspace?: string;
}

/** Title format function signature */
export type TitleFormatFunction = (ctx: TitleFormatContext) => string;

/** Parse and validate app configuration */
export function parseAppConfig(config: unknown): AppConfig;

/** Safely parse app configuration (returns success/error result) */
export function safeParseAppConfig(config: unknown): z.SafeParseReturnType<unknown, AppConfig>;

/** Props for ConfigProvider component */
export interface ConfigProviderProps {
  /** Raw configuration object (will be validated and merged with defaults) */
  config?: unknown;
  /** Child components */
  children: React.ReactNode;
}

/**
 * ConfigProvider component that provides validated configuration to the app
 *
 * @example
 * ```jsx
 * import { ConfigProvider } from './config'
 *
 * <ConfigProvider config={appConfig}>
 *   <App />
 * </ConfigProvider>
 * ```
 */
export function ConfigProvider(props: ConfigProviderProps): React.ReactElement;

/**
 * Hook to access the full application configuration
 * Must be used within a ConfigProvider
 *
 * @returns The validated configuration object
 * @throws Error if used outside of ConfigProvider
 *
 * @example
 * ```jsx
 * const { branding, features } = useConfig();
 * ```
 */
export function useConfig(): AppConfig;

/**
 * Hook to access a specific configuration value using dot-notation path
 *
 * @param path - Dot-notation path to the config value (e.g., 'branding.name')
 * @returns The value at the specified path, or undefined if not found
 * @throws Error if used outside of ConfigProvider
 *
 * @example
 * ```jsx
 * const appName = useConfigValue('branding.name');
 * const hasSearch = useConfigValue('features.search');
 * ```
 */
export function useConfigValue<T = unknown>(path: string): T | undefined;
