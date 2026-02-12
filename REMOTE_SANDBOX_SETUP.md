# Remote Sandbox Setup Guide

## Architecture

**File operations** and **chat agents** are completely independent:

```
┌─────────────────────────────────────────┐
│         Boring UI Backend               │
├─────────────────────────────────────────┤
│                                         │
│  File Operations:                       │
│  ├─ LocalStorage                        │
│  └─ Reads/writes to WORKSPACE_ROOT      │
│                                         │
│  Chat Agents (independent):             │
│  ├─ Claude Code                         │
│  ├─ Sandbox Agent                       │
│  └─ Companion                           │
│                                         │
└─────────────────────────────────────────┘
         │                          │
         └─ WORKSPACE_ROOT          └─ Agent Service
            (any filesystem)           (independent)
```

## How File Operations Work

1. **Set `WORKSPACE_ROOT`** to point to your filesystem
   - Local machine: `/home/ubuntu/projects`
   - Remote mounted: `/mnt/remote-sandbox`
   - Sprites mounted: `/mnt/sprites-workspace`

2. **`LocalStorage` handles all file I/O**
   - List files
   - Create files
   - Read/write content
   - Delete files
   - No special code needed!

3. **Works with any filesystem** as long as it's accessible on the backend machine
   - Local paths
   - NFS mounts
   - SSHFS mounts
   - Sprites.dev mounted filesystems
   - Any mounted remote storage

## Setup with Sprites.dev Remote Sandbox

### Step 1: Mount Sprites Workspace on Backend

On your backend machine, mount the Sprites.dev workspace:

```bash
# Example: Mount Sprites VM filesystem via SSHFS
mkdir -p /mnt/remote-sandbox
sshfs user@sprites-vm:/home/sprite/workspace /mnt/remote-sandbox

# Or via NFS if Sprites.dev exports it
mount -t nfs sprites-vm:/home/sprite/workspace /mnt/remote-sandbox
```

### Step 2: Start Backend Pointing to Mounted Path

```bash
WORKSPACE_ROOT=/mnt/remote-sandbox \
ANTHROPIC_API_KEY=$KEY \
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(
    include_sandbox=True,  # Sandbox agent (independent)
    include_companion=False,
)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

### Step 3: FileTree Now Works on Remote Workspace

- ✅ File list shows contents of `/mnt/remote-sandbox`
- ✅ File creation happens in `/mnt/remote-sandbox`
- ✅ All file operations work on the mounted Sprites filesystem
- ✅ **Sandbox agent is independent** - runs where you configured it

## Key Points

✅ **No special storage classes** - `LocalStorage` handles any mounted filesystem
✅ **Simple configuration** - Just set `WORKSPACE_ROOT` to the path
✅ **Agent is independent** - Configured separately, not tied to filesystem
✅ **Works with any mount** - NFS, SSHFS, Sprites, etc.
✅ **Same API** - FileTree operations work identically regardless of where workspace lives

## Example: Complete Setup

```bash
#!/bin/bash

# 1. Mount Sprites workspace
mkdir -p /mnt/remote-sandbox
sshfs sprite-user@sprites.dev:/home/sprite/workspace /mnt/remote-sandbox

# 2. Start backend with mounted path
export WORKSPACE_ROOT=/mnt/remote-sandbox
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)

# Backend
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
" &

# 3. Start frontend
npx vite --host 0.0.0.0 --port 5173 &

# Open browser
# http://localhost:5173

# FileTree shows: /mnt/remote-sandbox contents (which is Sprites.dev workspace)
# Agent: Runs independently (local or on Sprites)
```

## Troubleshooting

**Mount permission denied?**
```bash
# Check permissions on Sprites side
ssh sprite-user@sprites.dev "ls -la /home/sprite/workspace"

# Try with proper user/options
sshfs -o allow_other sprite-user@sprites.dev:/home/sprite/workspace /mnt/remote-sandbox
```

**FileTree shows empty?**
```bash
# Verify mount is working
ls -la /mnt/remote-sandbox

# Verify WORKSPACE_ROOT is set
echo $WORKSPACE_ROOT
```

**Agent not responding?**
- Agent is independent - verify its configuration separately
- Check if sandbox-agent is running on the configured machine
- Check firewall/network access to agent service
