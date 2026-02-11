# Boring UI - Workspace Configuration

## Overview

The FileTree file operations (list, create, read, write, delete) are **completely independent** of the chat agent. You can configure them to work with any filesystem:

- **Local Machine**: `/home/ubuntu/projects/boring-ui`
- **Sprites.dev VM**: `/home/sprite/my-project`
- **Any mounted filesystem**: `/mnt/remote-storage`

## How It Works

The `WORKSPACE_ROOT` environment variable tells the backend where to read and write files:

```bash
WORKSPACE_ROOT=/path/to/files python3 -c "..."
```

The backend uses `LocalStorage` which simply reads/writes to that path. **The filesystem location doesn't matter** - it could be local, remote via SSH mount, Sprites, or anywhere else.

## Usage Examples

### Example 1: Local Workspace (Default)
```bash
./START_WITH_WORKSPACE.sh /home/ubuntu/projects/boring-ui
```
- FileTree lists files from: `/home/ubuntu/projects/boring-ui`
- File creation happens in: `/home/ubuntu/projects/boring-ui`

### Example 2: Temporary Workspace (Isolation)
```bash
WORKSPACE_ROOT=/tmp/boring-workspace npx vite --host 0.0.0.0 --port 5173
```
- FileTree lists files from: `/tmp/boring-workspace`
- Each session has isolated files

### Example 3: Sprites.dev Workspace
```bash
WORKSPACE_ROOT=/home/sprite/my-project python3 -c "from boring_ui.api.app import create_app; ..."
```
- FileTree lists files from: `/home/sprite/my-project` (on Sprites.dev VM)
- File creation happens in: `/home/sprite/my-project`
- **Requires**: The Sprites filesystem is mounted or accessible on the backend machine

### Example 4: Mounted Remote Filesystem
```bash
WORKSPACE_ROOT=/mnt/sprites-share/user1 python3 -c "..."
```
- FileTree lists files from: `/mnt/sprites-share/user1` (mounted via NFS/SMB)
- Works with any mount point

## Agent Configuration (Independent)

The **chat agent** is configured **separately** from the filesystem:

```bash
# Backend with custom workspace + sandbox agent
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(
    include_sandbox=True,        # Sandbox agent for chat
    include_companion=False,
)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

The agent runs wherever you configure it (local subprocess, Sprites VM, etc.) and is **independent** of where files are stored.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Boring UI Frontend (Browser)       │
├─────────────────────────────────────────────────┤
│
│  FileTree API calls:                Chat API calls:
│  GET  /api/tree    ──┐              /ws/chat ──┐
│  POST /api/file    ──┤              (Agent API)│
│  DELETE /api/file  ──┤                        │
│                      │                         │
├────────────────────┬─┴─────────────────────────┤
│      Backend       │         Agents            │
│   (FastAPI)        │                           │
│                    │                           │
│  ┌──────────────┐  │  ┌──────────────────────┐│
│  │ FileService  │  │  │ Agent Service        ││
│  │              │  │  │ (Claude, Sandbox,    ││
│  └──┬───────────┘  │  │  Companion, etc.)    ││
│     │              │  └──────────────────────┘│
│     │              │                          │
│  LocalStorage      │  ┌──────────────────────┐│
│  ├─ workspace      │  │ Sandbox-Agent        ││
│  │  (any path)     │  │ (Port 2468)          ││
│  └─ File I/O       │  │ (Independent)        ││
│                    │  └──────────────────────┘│
└────────────────────┴──────────────────────────┘
         │
         └─> WORKSPACE_ROOT
             ├─ Local: /home/ubuntu/projects
             ├─ Sprites: /home/sprite/my-project
             ├─ Mounted: /mnt/remote-storage
             └─ Any filesystem path
```

## Key Points

✅ **FileTree operations** (list, create, read, write) work on `WORKSPACE_ROOT`
✅ **Chat agents** are configured independently
✅ **Multiple workspaces** can be used with different `WORKSPACE_ROOT` values
✅ **No special storage classes needed** - just plain file I/O on any path
✅ **Works with local, Sprites, NFS, SMB, or any mounted filesystem**

## Startup Examples

### Using the startup script
```bash
./START_WITH_WORKSPACE.sh /home/sprite/my-workspace
```

### Or directly
```bash
WORKSPACE_ROOT=/home/sprite/my-workspace \
ANTHROPIC_API_KEY=$KEY \
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

## Summary

- **Don't create special Storage classes** - `LocalStorage` handles any path
- **Set `WORKSPACE_ROOT`** to point to your files (local, Sprites, or mounted)
- **Configure agents independently** - they're not tied to the workspace
- **Same API regardless** - FileTree works the same whether workspace is local or remote
