import { z } from 'zod';

/**
 * Zod schema for app.config.js
 * Defines the structure and validation rules for the application configuration
 */

// Branding configuration schema
export const brandingSchema = z.object({
  name: z.string().default('My App'),
  logo: z.union([z.string(), z.any()]).default('M'), // string or React component
  // titleFormat is a function: (ctx: { folder?: string, workspace?: string }) => string
  titleFormat: z.any().optional().default(() => (ctx) => ctx.workspace ? `${ctx.workspace} - My App` : 'My App'),
});

// FileTree section schema
export const fileTreeSectionSchema = z.object({
  key: z.string(),
  label: z.string(),
  icon: z.string(),
});

// FileTree configuration schema
export const fileTreeSchema = z.object({
  sections: z.array(fileTreeSectionSchema).default([]),
  configFiles: z.array(z.string()).default([]),
  gitPollInterval: z.number().int().positive().default(5000),
  treePollInterval: z.number().int().positive().default(3000),
});

// Storage configuration schema
export const storageSchema = z.object({
  prefix: z.string().default('myapp'),
  layoutVersion: z.number().int().nonnegative().default(1),
  migrateLegacyKeys: z.record(z.string(), z.string()).optional(),
});

// Panels configuration schema
export const panelsSchema = z.object({
  essential: z.array(z.string()).default(['filetree', 'terminal']),
  defaults: z.record(z.string(), z.number()).default({
    filetree: 280,
    terminal: 400,
  }),
  min: z.record(z.string(), z.number()).default({
    filetree: 180,
    terminal: 250,
  }),
  collapsed: z.record(z.string(), z.number()).default({
    filetree: 48,
    terminal: 48,
  }),
});

// API configuration schema
export const apiSchema = z.object({
  baseUrl: z.string().default(''),
});

// Features configuration schema
export const featuresSchema = z.object({
  gitStatus: z.boolean().default(true),
  search: z.boolean().default(true),
  cloudMode: z.boolean().default(true),
  workflows: z.boolean().default(false),
});

// Complete app configuration schema
export const appConfigSchema = z.object({
  branding: brandingSchema.default({}),
  fileTree: fileTreeSchema.default({}),
  storage: storageSchema.default({}),
  panels: panelsSchema.default({}),
  api: apiSchema.default({}),
  features: featuresSchema.default({}),
});

/**
 * Validate and parse app configuration
 * @param {unknown} config - Raw configuration object
 * @returns {AppConfig} Validated configuration with defaults applied
 */
export function parseAppConfig(config) {
  return appConfigSchema.parse(config);
}

/**
 * Safely validate app configuration (returns success/error result)
 * @param {unknown} config - Raw configuration object
 * @returns {z.SafeParseReturnType<unknown, AppConfig>} Parse result
 */
export function safeParseAppConfig(config) {
  return appConfigSchema.safeParse(config);
}
