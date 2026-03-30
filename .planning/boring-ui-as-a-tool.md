# Making boring-ui a Tool

**Goal**: Make boring-ui programmable and automatable - CLI, API, SDK, MCP server

**Status**: Draft
**Created**: 2026-03-29
**Timeline**: 4-6 weeks

---

## Vision

**Current**: boring-ui is a web app you visit in a browser
**Goal**: boring-ui is a **tool** that agents, scripts, and other apps can use

### Use Cases

1. **CI/CD Integration**: Run tests in a boring-ui workspace from GitHub Actions
2. **Agent Tool**: AI agents can create workspaces, run code, get results
3. **Automation**: Scripts can automate workspace operations
4. **Embedding**: Other apps can embed boring-ui workspaces
5. **MCP Server**: Claude Desktop can use boring-ui as an execution environment

---

## What Does "Tool" Mean?

### 1. CLI Tool (`bui`)
```bash
# Create workspace
bui workspace create my-project

# Execute command
bui exec "npm test" --workspace my-project

# Get file
bui file read src/index.ts --workspace my-project

# Run agent
bui agent "fix all TypeScript errors"
```

### 2. REST API (Already Exists!)
```bash
# Create workspace
curl -X POST https://boring-ui.app/api/v1/workspaces \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "my-project"}'

# Execute command
curl -X POST https://boring-ui.app/api/v1/workspaces/abc/exec \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"command": "npm test"}'
```

### 3. SDK (TypeScript/Python)
```typescript
import { BoringUI } from '@boring-ui/sdk'

const client = new BoringUI({ apiKey: process.env.BORING_UI_API_KEY })

// Create workspace
const workspace = await client.workspaces.create({ name: 'my-project' })

// Execute command
const result = await workspace.exec('npm test')
console.log(result.stdout)

// Agent execution
const agentResult = await workspace.agent('fix all TypeScript errors')
```

### 4. MCP Server
```json
// Claude Desktop can use boring-ui as an execution environment
{
  "mcpServers": {
    "boring-ui": {
      "command": "npx",
      "args": ["@boring-ui/mcp-server"]
    }
  }
}
```

Claude can then:
```
User: "Create a new Node.js project and run tests"
Claude: [uses boring-ui MCP tool to create workspace, write code, run tests]
```

---

## Phase 1: CLI Tool (`bui`) - 2 weeks

**Goal**: Command-line interface for workspace automation

### 1.1 CLI Package Structure

```
packages/bui-cli/
├── package.json
├── src/
│   ├── index.ts          # Entry point
│   ├── commands/
│   │   ├── workspace.ts  # workspace create/list/delete
│   │   ├── exec.ts       # Execute commands
│   │   ├── file.ts       # File operations
│   │   ├── git.ts        # Git operations
│   │   └── agent.ts      # AI agent operations
│   ├── client.ts         # API client
│   └── config.ts         # Config management (~/.bui/config.json)
└── bin/
    └── bui               # Executable
```

### 1.2 Core Commands

**Workspace Management**
```bash
bui workspace create <name>              # Create workspace
bui workspace list                       # List workspaces
bui workspace delete <id>                # Delete workspace
bui workspace status <id>                # Get workspace status
bui workspace connect <id>               # Open in browser
```

**File Operations**
```bash
bui file read <path> -w <workspace>      # Read file
bui file write <path> -w <workspace>     # Write file (from stdin)
bui file list -w <workspace>             # List files
bui file tree -w <workspace>             # Show file tree
```

**Execution**
```bash
bui exec "npm test" -w <workspace>       # Run command
bui exec "npm test" -w <workspace> -f    # Follow output (stream)
bui exec "npm test" -w <workspace> -d    # Detached (background)
```

**Git Operations**
```bash
bui git status -w <workspace>            # Git status
bui git commit -m "msg" -w <workspace>   # Git commit
bui git push -w <workspace>              # Git push
```

**AI Agent**
```bash
bui agent "fix all linting errors" -w <workspace>
bui agent "write tests for src/index.ts" -w <workspace>
bui agent "implement feature X" -w <workspace>
```

**Configuration**
```bash
bui config set api-url https://boring-ui.app
bui config set api-key sk-bui-...
bui config get api-url
bui login                                # Interactive login
```

### 1.3 Implementation

**File**: `packages/bui-cli/src/index.ts`

```typescript
#!/usr/bin/env node
import { Command } from 'commander'
import { BoringUIClient } from './client.js'
import { loadConfig } from './config.js'

const program = new Command()

program
  .name('bui')
  .description('boring-ui CLI - Programmable workspace automation')
  .version('1.0.0')

// Workspace commands
program
  .command('workspace')
  .description('Manage workspaces')
  .command('create <name>')
  .action(async (name) => {
    const config = await loadConfig()
    const client = new BoringUIClient(config)

    const workspace = await client.workspaces.create({ name })
    console.log(`✓ Workspace created: ${workspace.id}`)
    console.log(`  URL: ${config.apiUrl}/workspace/${workspace.id}`)
  })

// Exec command
program
  .command('exec <command>')
  .option('-w, --workspace <id>', 'Workspace ID')
  .option('-f, --follow', 'Follow output')
  .action(async (command, options) => {
    const config = await loadConfig()
    const client = new BoringUIClient(config)

    if (options.follow) {
      // Stream output
      await client.exec.stream(options.workspace, command, {
        onData: (data) => process.stdout.write(data),
        onError: (err) => process.stderr.write(err),
        onExit: (code) => process.exit(code)
      })
    } else {
      // Wait for completion
      const result = await client.exec.run(options.workspace, command)
      console.log(result.stdout)
      if (result.stderr) console.error(result.stderr)
      process.exit(result.exitCode)
    }
  })

// File operations
program
  .command('file')
  .command('read <path>')
  .option('-w, --workspace <id>', 'Workspace ID')
  .action(async (path, options) => {
    const config = await loadConfig()
    const client = new BoringUIClient(config)

    const content = await client.files.read(options.workspace, path)
    console.log(content)
  })

// Agent command
program
  .command('agent <prompt>')
  .option('-w, --workspace <id>', 'Workspace ID')
  .option('-f, --follow', 'Follow agent progress')
  .action(async (prompt, options) => {
    const config = await loadConfig()
    const client = new BoringUIClient(config)

    console.log('🤖 Agent working...')

    const result = await client.agent.run(options.workspace, prompt, {
      onProgress: (msg) => console.log(`  ${msg}`)
    })

    console.log('\n✓ Agent complete')
    console.log(result.summary)
  })

program.parse()
```

**API Client**: `packages/bui-cli/src/client.ts`

```typescript
export class BoringUIClient {
  private apiUrl: string
  private apiKey: string

  constructor(config: Config) {
    this.apiUrl = config.apiUrl
    this.apiKey = config.apiKey
  }

  workspaces = {
    create: async (opts: { name: string }) => {
      const res = await fetch(`${this.apiUrl}/api/v1/workspaces`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(opts)
      })
      return await res.json()
    },

    list: async () => {
      const res = await fetch(`${this.apiUrl}/api/v1/workspaces`, {
        headers: { 'Authorization': `Bearer ${this.apiKey}` }
      })
      return await res.json()
    },

    delete: async (id: string) => {
      await fetch(`${this.apiUrl}/api/v1/workspaces/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${this.apiKey}` }
      })
    }
  }

  files = {
    read: async (workspaceId: string, path: string) => {
      const res = await fetch(
        `${this.apiUrl}/api/v1/workspaces/${workspaceId}/files?path=${encodeURIComponent(path)}`,
        { headers: { 'Authorization': `Bearer ${this.apiKey}` } }
      )
      return await res.text()
    },

    write: async (workspaceId: string, path: string, content: string) => {
      await fetch(`${this.apiUrl}/api/v1/workspaces/${workspaceId}/files`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ path, content })
      })
    }
  }

  exec = {
    run: async (workspaceId: string, command: string) => {
      const res = await fetch(`${this.apiUrl}/api/v1/workspaces/${workspaceId}/exec`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command })
      })
      return await res.json()
    },

    stream: async (workspaceId: string, command: string, callbacks: {
      onData: (data: string) => void
      onError: (err: string) => void
      onExit: (code: number) => void
    }) => {
      // WebSocket streaming
      const ws = new WebSocket(
        `${this.apiUrl.replace('http', 'ws')}/api/v1/workspaces/${workspaceId}/exec/stream`,
        { headers: { 'Authorization': `Bearer ${this.apiKey}` } }
      )

      ws.on('open', () => {
        ws.send(JSON.stringify({ command }))
      })

      ws.on('message', (data) => {
        const msg = JSON.parse(data.toString())
        if (msg.type === 'stdout') callbacks.onData(msg.data)
        if (msg.type === 'stderr') callbacks.onError(msg.data)
        if (msg.type === 'exit') callbacks.onExit(msg.code)
      })
    }
  }

  agent = {
    run: async (workspaceId: string, prompt: string, callbacks?: {
      onProgress?: (msg: string) => void
    }) => {
      const res = await fetch(`${this.apiUrl}/api/v1/workspaces/${workspaceId}/agent`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt })
      })

      // Stream agent progress
      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(l => l.trim())

        for (const line of lines) {
          const msg = JSON.parse(line)
          if (msg.type === 'progress' && callbacks?.onProgress) {
            callbacks.onProgress(msg.message)
          }
          if (msg.type === 'complete') {
            return msg.result
          }
        }
      }
    }
  }
}
```

### 1.4 Configuration

**File**: `~/.bui/config.json`

```json
{
  "apiUrl": "https://boring-ui.app",
  "apiKey": "sk-bui-...",
  "defaultWorkspace": "abc123"
}
```

**Login flow**:
```bash
bui login
# Opens browser → OAuth → Stores API key
```

### Success Criteria
- [ ] CLI installed via `npm install -g @boring-ui/cli`
- [ ] Can create workspace from CLI
- [ ] Can execute commands and get output
- [ ] Can read/write files
- [ ] Agent integration works

---

## Phase 2: TypeScript/JavaScript SDK - 1 week

**Goal**: Embeddable SDK for programmatic access

### 2.1 SDK Package

**File**: `packages/boring-ui-sdk/src/index.ts`

```typescript
export class BoringUI {
  private client: APIClient

  constructor(options: { apiKey: string; apiUrl?: string }) {
    this.client = new APIClient(options)
  }

  workspaces = {
    create: async (opts: CreateWorkspaceOpts) => {
      const data = await this.client.post('/workspaces', opts)
      return new Workspace(this.client, data)
    },

    get: async (id: string) => {
      const data = await this.client.get(`/workspaces/${id}`)
      return new Workspace(this.client, data)
    },

    list: async () => {
      const data = await this.client.get('/workspaces')
      return data.map(w => new Workspace(this.client, w))
    }
  }
}

export class Workspace {
  id: string
  name: string

  constructor(private client: APIClient, data: any) {
    this.id = data.id
    this.name = data.name
  }

  async exec(command: string): Promise<ExecResult> {
    return await this.client.post(`/workspaces/${this.id}/exec`, { command })
  }

  async readFile(path: string): Promise<string> {
    return await this.client.get(`/workspaces/${this.id}/files?path=${path}`)
  }

  async writeFile(path: string, content: string): Promise<void> {
    await this.client.put(`/workspaces/${this.id}/files`, { path, content })
  }

  async agent(prompt: string): Promise<AgentResult> {
    return await this.client.post(`/workspaces/${this.id}/agent`, { prompt })
  }

  async delete(): Promise<void> {
    await this.client.delete(`/workspaces/${this.id}`)
  }
}
```

**Usage**:
```typescript
import { BoringUI } from '@boring-ui/sdk'

const bui = new BoringUI({ apiKey: process.env.BORING_UI_API_KEY })

// Create workspace
const workspace = await bui.workspaces.create({ name: 'test-project' })

// Write code
await workspace.writeFile('test.js', `
  console.log('Hello from boring-ui!')
`)

// Run it
const result = await workspace.exec('node test.js')
console.log(result.stdout) // "Hello from boring-ui!"

// Use agent
const fixed = await workspace.agent('fix all eslint errors')
console.log(fixed.summary)

// Cleanup
await workspace.delete()
```

### Success Criteria
- [ ] SDK published to npm as `@boring-ui/sdk`
- [ ] TypeScript types included
- [ ] Works in Node.js and browsers
- [ ] Example apps using SDK

---

## Phase 3: Python SDK - 1 week

**Goal**: Python client for data science / automation use cases

**File**: `packages/boring-ui-python/boring_ui/__init__.py`

```python
from typing import Optional
import requests

class BoringUI:
    def __init__(self, api_key: str, api_url: str = "https://boring-ui.app"):
        self.api_key = api_key
        self.api_url = api_url
        self.workspaces = WorkspacesAPI(self)

class WorkspacesAPI:
    def __init__(self, client: BoringUI):
        self.client = client

    def create(self, name: str) -> 'Workspace':
        res = requests.post(
            f"{self.client.api_url}/api/v1/workspaces",
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            json={"name": name}
        )
        return Workspace(self.client, res.json())

    def get(self, id: str) -> 'Workspace':
        res = requests.get(
            f"{self.client.api_url}/api/v1/workspaces/{id}",
            headers={"Authorization": f"Bearer {self.client.api_key}"}
        )
        return Workspace(self.client, res.json())

class Workspace:
    def __init__(self, client: BoringUI, data: dict):
        self.client = client
        self.id = data['id']
        self.name = data['name']

    def exec(self, command: str) -> dict:
        res = requests.post(
            f"{self.client.api_url}/api/v1/workspaces/{self.id}/exec",
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            json={"command": command}
        )
        return res.json()

    def read_file(self, path: str) -> str:
        res = requests.get(
            f"{self.client.api_url}/api/v1/workspaces/{self.id}/files",
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            params={"path": path}
        )
        return res.text

    def write_file(self, path: str, content: str):
        requests.put(
            f"{self.client.api_url}/api/v1/workspaces/{self.id}/files",
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            json={"path": path, "content": content}
        )

    def agent(self, prompt: str) -> dict:
        res = requests.post(
            f"{self.client.api_url}/api/v1/workspaces/{self.id}/agent",
            headers={"Authorization": f"Bearer {self.client.api_key}"},
            json={"prompt": prompt}
        )
        return res.json()

    def delete(self):
        requests.delete(
            f"{self.client.api_url}/api/v1/workspaces/{self.id}",
            headers={"Authorization": f"Bearer {self.client.api_key}"}
        )
```

**Usage**:
```python
from boring_ui import BoringUI

bui = BoringUI(api_key="sk-bui-...")

# Create workspace
workspace = bui.workspaces.create("data-analysis")

# Write Python script
workspace.write_file("analysis.py", """
import pandas as pd
df = pd.read_csv('data.csv')
print(df.describe())
""")

# Run it
result = workspace.exec("python analysis.py")
print(result['stdout'])

# Use agent
workspace.agent("create a visualization of the data")

# Cleanup
workspace.delete()
```

### Success Criteria
- [ ] Published to PyPI as `boring-ui`
- [ ] Type hints included
- [ ] Works with Python 3.8+
- [ ] Jupyter notebook examples

---

## Phase 4: MCP Server - 2 weeks

**Goal**: boring-ui as an MCP server for Claude Desktop

### 4.1 MCP Server Package

**File**: `packages/boring-ui-mcp/src/index.ts`

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { BoringUI } from '@boring-ui/sdk'

const server = new Server(
  {
    name: 'boring-ui',
    version: '1.0.0'
  },
  {
    capabilities: {
      tools: {}
    }
  }
)

const bui = new BoringUI({
  apiKey: process.env.BORING_UI_API_KEY!
})

// Tool: Create workspace
server.setRequestHandler('tools/call', async (request) => {
  if (request.params.name === 'boring_ui_create_workspace') {
    const { name } = request.params.arguments as { name: string }
    const workspace = await bui.workspaces.create({ name })

    return {
      content: [{
        type: 'text',
        text: JSON.stringify({ workspaceId: workspace.id, url: `https://boring-ui.app/workspace/${workspace.id}` })
      }]
    }
  }

  // Tool: Execute command
  if (request.params.name === 'boring_ui_exec') {
    const { workspaceId, command } = request.params.arguments as { workspaceId: string, command: string }
    const workspace = await bui.workspaces.get(workspaceId)
    const result = await workspace.exec(command)

    return {
      content: [{
        type: 'text',
        text: JSON.stringify(result)
      }]
    }
  }

  // Tool: Read file
  if (request.params.name === 'boring_ui_read_file') {
    const { workspaceId, path } = request.params.arguments as { workspaceId: string, path: string }
    const workspace = await bui.workspaces.get(workspaceId)
    const content = await workspace.readFile(path)

    return {
      content: [{
        type: 'text',
        text: content
      }]
    }
  }

  // Tool: Write file
  if (request.params.name === 'boring_ui_write_file') {
    const { workspaceId, path, content } = request.params.arguments as { workspaceId: string, path: string, content: string }
    const workspace = await bui.workspaces.get(workspaceId)
    await workspace.writeFile(path, content)

    return {
      content: [{
        type: 'text',
        text: 'File written successfully'
      }]
    }
  }

  throw new Error(`Unknown tool: ${request.params.name}`)
})

// List available tools
server.setRequestHandler('tools/list', async () => {
  return {
    tools: [
      {
        name: 'boring_ui_create_workspace',
        description: 'Create a new boring-ui workspace for code execution',
        inputSchema: {
          type: 'object',
          properties: {
            name: { type: 'string', description: 'Workspace name' }
          },
          required: ['name']
        }
      },
      {
        name: 'boring_ui_exec',
        description: 'Execute a command in a boring-ui workspace',
        inputSchema: {
          type: 'object',
          properties: {
            workspaceId: { type: 'string', description: 'Workspace ID' },
            command: { type: 'string', description: 'Command to execute' }
          },
          required: ['workspaceId', 'command']
        }
      },
      {
        name: 'boring_ui_read_file',
        description: 'Read a file from a boring-ui workspace',
        inputSchema: {
          type: 'object',
          properties: {
            workspaceId: { type: 'string' },
            path: { type: 'string' }
          },
          required: ['workspaceId', 'path']
        }
      },
      {
        name: 'boring_ui_write_file',
        description: 'Write a file to a boring-ui workspace',
        inputSchema: {
          type: 'object',
          properties: {
            workspaceId: { type: 'string' },
            path: { type: 'string' },
            content: { type: 'string' }
          },
          required: ['workspaceId', 'path', 'content']
        }
      }
    ]
  }
})

// Start server
const transport = new StdioServerTransport()
await server.connect(transport)
```

### 4.2 Claude Desktop Configuration

**File**: `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac)

```json
{
  "mcpServers": {
    "boring-ui": {
      "command": "npx",
      "args": ["@boring-ui/mcp-server"],
      "env": {
        "BORING_UI_API_KEY": "sk-bui-..."
      }
    }
  }
}
```

### 4.3 Usage Example

User talks to Claude Desktop:

```
User: Create a Node.js project that fetches data from an API

Claude: I'll create a boring-ui workspace and implement this for you.

[Claude uses boring_ui_create_workspace tool]
[Claude uses boring_ui_write_file to create package.json]
[Claude uses boring_ui_write_file to create index.js]
[Claude uses boring_ui_exec to run npm install]
[Claude uses boring_ui_exec to test the code]

Claude: ✓ I've created a Node.js project in workspace abc123.
       You can view it at https://boring-ui.app/workspace/abc123

       The project fetches data from https://api.example.com and
       prints the results. I've tested it and it works!
```

### Success Criteria
- [ ] MCP server published as `@boring-ui/mcp-server`
- [ ] Works in Claude Desktop
- [ ] Claude can create workspaces, write code, execute
- [ ] Example prompts documented

---

## Phase 5: API Keys & Authentication - 1 week

**Goal**: API key generation for CLI/SDK access

### 5.1 API Keys Table

```sql
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,  -- bcrypt hash
  key_prefix TEXT NOT NULL,  -- First 8 chars for display
  scopes TEXT[] NOT NULL DEFAULT ARRAY['read', 'write'],
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  revoked_at TIMESTAMP
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
```

### 5.2 API Key Generation

**UI**: `src/front/pages/Settings.jsx`

```jsx
function APIKeysSection() {
  const [keys, setKeys] = useState([])

  async function generateKey() {
    const name = prompt('Key name (e.g., "CI/CD", "CLI")')
    const res = await fetch('/api/v1/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name })
    })
    const { key } = await res.json()

    // Show key ONCE (never stored in plain text)
    alert(`API Key (save this now!):\n\n${key}`)

    fetchKeys()
  }

  return (
    <div>
      <h2>API Keys</h2>
      <button onClick={generateKey}>Generate New Key</button>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Key</th>
            <th>Created</th>
            <th>Last Used</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {keys.map(key => (
            <tr key={key.id}>
              <td>{key.name}</td>
              <td>{key.keyPrefix}...</td>
              <td>{formatDate(key.createdAt)}</td>
              <td>{key.lastUsedAt ? formatDate(key.lastUsedAt) : 'Never'}</td>
              <td>
                <button onClick={() => revokeKey(key.id)}>Revoke</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

### 5.3 Authentication Middleware

**File**: `src/server/middleware/apiKeyAuth.ts`

```typescript
export function apiKeyAuth() {
  return async (req, reply) => {
    const authHeader = req.headers.authorization

    if (!authHeader?.startsWith('Bearer sk-bui-')) {
      return reply.code(401).send({ error: 'Invalid API key' })
    }

    const apiKey = authHeader.replace('Bearer ', '')

    // Hash and lookup
    const keyHash = await bcrypt.hash(apiKey, 10)
    const key = await db.query.apiKeys.findFirst({
      where: eq(apiKeys.keyHash, keyHash)
    })

    if (!key || key.revokedAt) {
      return reply.code(401).send({ error: 'Invalid API key' })
    }

    if (key.expiresAt && new Date(key.expiresAt) < new Date()) {
      return reply.code(401).send({ error: 'API key expired' })
    }

    // Update last used
    await db.update(apiKeys)
      .set({ lastUsedAt: new Date() })
      .where(eq(apiKeys.id, key.id))

    // Attach user to request
    req.user = await db.query.users.findFirst({
      where: eq(users.id, key.userId)
    })
  }
}
```

### Success Criteria
- [ ] Users can generate API keys in settings
- [ ] API keys work with CLI/SDK
- [ ] Keys can be revoked
- [ ] Last used timestamp tracked

---

## Use Cases & Examples

### 1. CI/CD Integration

**GitHub Actions**:
```yaml
name: Test
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Test in boring-ui
        env:
          BORING_UI_API_KEY: ${{ secrets.BORING_UI_API_KEY }}
        run: |
          npm install -g @boring-ui/cli
          bui workspace create ci-test-${{ github.run_id }}
          bui exec "npm install && npm test" -w ci-test-${{ github.run_id }}
          bui workspace delete ci-test-${{ github.run_id }}
```

### 2. Agent Tool

**LangChain integration**:
```typescript
import { BoringUI } from '@boring-ui/sdk'
import { Tool } from 'langchain/tools'

class BoringUITool extends Tool {
  name = 'boring-ui'
  description = 'Execute code in a sandboxed environment'

  private bui = new BoringUI({ apiKey: process.env.BORING_UI_API_KEY })
  private workspace: Workspace

  async _call(code: string) {
    if (!this.workspace) {
      this.workspace = await this.bui.workspaces.create({ name: 'agent-workspace' })
    }

    await this.workspace.writeFile('script.js', code)
    const result = await this.workspace.exec('node script.js')

    return result.stdout
  }
}

// Use in agent
const agent = new Agent({
  tools: [new BoringUITool()]
})

await agent.run('Calculate the sum of all prime numbers under 1000')
// Agent writes code, executes in boring-ui, returns result
```

### 3. Notebook Integration

**Jupyter notebook**:
```python
from boring_ui import BoringUI

bui = BoringUI(api_key="sk-bui-...")
workspace = bui.workspaces.create("analysis")

# Write data
workspace.write_file("data.csv", df.to_csv())

# Run analysis in boring-ui
workspace.write_file("analyze.py", """
import pandas as pd
df = pd.read_csv('data.csv')
print(df.describe())
""")

result = workspace.exec("python analyze.py")
print(result['stdout'])
```

---

## Timeline

```
Week 1-2:   CLI tool (bui)
Week 3:     TypeScript SDK
Week 4:     Python SDK
Week 5-6:   MCP server
Week 7:     API key system
Week 8:     Docs, examples, testing
```

**Total: 4-6 weeks**

---

## Success Metrics

- [ ] CLI tool published and working
- [ ] SDK published (TS + Python)
- [ ] MCP server works in Claude Desktop
- [ ] 10+ example use cases documented
- [ ] API key management in UI
- [ ] CI/CD integration example
- [ ] Agent integration example

---

## Benefits

✅ **Automation**: Scripts can use boring-ui
✅ **CI/CD**: Test in isolated environments
✅ **Agent Tool**: AI agents can execute code safely
✅ **Embedding**: Other apps can integrate boring-ui
✅ **Programmatic**: Everything via API

**boring-ui becomes infrastructure, not just an app!**
