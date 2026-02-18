# Domain Deep-Dives

Detailed technical documentation on specific subsystems. Add a new file per domain as needed.

## Domains

| Domain | File | Description |
|---|---|---|
| File Operations | (planned) | Files module: CRUD, search, path security, storage backends |
| Git Integration | (planned) | Git module: status, diff, show, worktree awareness |
| Terminal/PTY | (planned) | PTY service: WebSocket lifecycle, provider model, session management |
| Chat Streaming | (planned) | Claude stream: WebSocket protocol, stream_bridge, agent sessions |
| Approval Workflow | (planned) | Tool approval: request/decision flow, policy enforcement |
| Layout System | (planned) | DockView layout: persistence, migration, validation, recovery |
| Pane Registry | (planned) | Registry pattern: registration, capability requirements, gating |
| Chat Providers | (planned) | Companion + PI: provider registry, embedded vs iframe modes |
| Transport Layer | (planned) | Frontend networking: apiBase, routes, transport, controlPlane |

## Contributing a Domain Doc

Create a file named `<domain>.md` in this directory. Structure:

```markdown
# <Domain Name>

## Overview
What this domain does and why it exists.

## Key Files
Table of files with their responsibilities.

## Data Flow
How data moves through the domain.

## API Surface
Endpoints, events, or interfaces this domain exposes.

## Edge Cases
Known quirks, limitations, and design trade-offs.
```
