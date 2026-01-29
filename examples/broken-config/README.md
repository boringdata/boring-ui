# Broken Config Example

This example demonstrates the config validation error UI.

## Usage

To see the validation error screen:

1. Start the boring-ui development server with this broken config
2. The app will display a "Configuration Error" page listing all validation issues

## What's broken

This config intentionally includes multiple validation errors:

- `branding.name` is a number instead of a string
- `fileTree.sections[0]` is missing required `label` and `icon` fields
- `fileTree.sections[1].key` is a number instead of a string
- `fileTree.gitPollInterval` is negative (must be positive)
- `fileTree.treePollInterval` is a string instead of a number
- `storage.layoutVersion` is negative (must be non-negative)
- `features.gitStatus` is a string instead of boolean
- `features.search` is a number instead of boolean
- `features.workflows` is a string instead of boolean

## Expected behavior

The ConfigProvider should:
1. Log ALL validation errors to the console (not just the first one)
2. Display a user-friendly error page with the list of issues
3. NOT render the app until the configuration is fixed
