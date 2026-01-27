# boring-ui

Reusable UI components for Boring Data apps. A configurable framework providing:

- **FileTree** - Configurable file browser with git status
- **ChatPanel** - Claude Code-style chat interface
- **Terminal** - Shell terminal with session management
- **Theme System** - Light/dark mode with design tokens
- **DockView Layout** - Flexible panel management

## Usage

Copy this folder to your project and configure via `app.config.js`:

```javascript
// app.config.js
export default {
  branding: {
    name: 'My App',
    logo: 'M',
  },
  fileTree: {
    sections: ['documents', 'queries', 'config'],
    icons: { documents: 'FileText', queries: 'Search', config: 'Settings' },
    configFiles: ['config.yaml'],
  },
  storage: {
    prefix: 'myapp',
  },
}
```

## Components

### Shared (copy as-is)
- `ThemeToggle` - Light/dark mode switcher
- `UserMenu` - User avatar with dropdown
- `ChatPanel` - Claude Code chat interface
- `Terminal` - xterm.js terminal wrapper
- `ShellTerminal` - Shell session terminal

### Configurable
- `Header` - App branding (logo, name)
- `FileTree` - File browser (sections, icons, config files)
- `DockLayout` - Panel arrangement

### App-Specific (examples, customize per app)
- `Editor` - TipTap/Monaco editor
- `PreviewPanel` - Content preview
- `WorkflowsPanel` - Workflow execution (kurt-core specific)

## Design Tokens

All styling uses CSS custom properties defined in `styles.css`:

```css
--color-accent: #3b82f6;
--color-bg-primary: #ffffff;
--font-sans: 'Inter', sans-serif;
/* etc. */
```

## License

MIT
