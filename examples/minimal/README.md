# Minimal boring-ui Example

A minimal example demonstrating how to use boring-ui components in a custom layout.

## Prerequisites

Before running this example, you need to build the boring-ui library:

```bash
# From the repository root
cd ../..
npm install
npm run build:lib
```

## Running the Example

1. Install dependencies:
```bash
npm install
```

2. Start the backend server:
```bash
python server.py
```

3. In another terminal, start the frontend:
```bash
npm run dev
```

4. Open http://localhost:5173 in your browser.

## What This Example Demonstrates

- Importing boring-ui components (`DockLayout`, `FileTreePanel`, `EditorPanel`, `ShellTerminalPanel`)
- Composing panels into a custom layout
- Setting up the Python backend with `create_app()`
- Vite proxy configuration for API and WebSocket endpoints
