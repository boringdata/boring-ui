# bd-1wi2.2.1: Copy vendored upstream Companion app from POC branch

*2026-02-14T21:27:36Z by Showboat 0.5.0*

```bash
ls -la src/front/providers/companion/upstream/
```

```output
total 72
drwxrwxr-x 4 ubuntu ubuntu  4096 Feb 14 20:41 .
drwxrwxr-x 4 ubuntu ubuntu  4096 Feb 14 20:46 ..
-rw-rw-r-- 1 ubuntu ubuntu  3207 Feb 14 20:41 App.tsx
-rw-rw-r-- 1 ubuntu ubuntu  5462 Feb 14 20:41 api.ts
drwxrwxr-x 2 ubuntu ubuntu  4096 Feb 14 20:41 components
-rw-rw-r-- 1 ubuntu ubuntu  2184 Feb 14 20:41 index.css
-rw-rw-r-- 1 ubuntu ubuntu   233 Feb 14 20:41 main.tsx
-rw-rw-r-- 1 ubuntu ubuntu 12671 Feb 14 20:41 store.ts
-rw-rw-r-- 1 ubuntu ubuntu  1120 Feb 14 20:41 types.ts
drwxrwxr-x 2 ubuntu ubuntu  4096 Feb 14 20:41 utils
-rw-rw-r-- 1 ubuntu ubuntu 14055 Feb 14 20:41 ws.ts
```

```bash
ls src/front/providers/companion/upstream/components/ src/front/providers/companion/upstream/utils/
```

```output
src/front/providers/companion/upstream/components/:
ChatView.tsx
Composer.tsx
EnvManager.tsx
HomePage.tsx
MessageBubble.tsx
MessageFeed.tsx
PermissionBanner.tsx
Playground.tsx
Sidebar.tsx
TaskPanel.tsx
ToolBlock.tsx
TopBar.tsx

src/front/providers/companion/upstream/utils/:
names.ts
```

```bash
find src/front/providers/companion/upstream/ -type f | wc -l && echo 'files copied from poc/opencode-web-chat branch'
```

```output
20
files copied from poc/opencode-web-chat branch
```

```bash
head -4 src/front/providers/companion/upstream/api.ts && echo '...' && grep 'import.*config' src/front/providers/companion/upstream/api.ts src/front/providers/companion/upstream/ws.ts
```

```output
import type { SdkSessionInfo } from "./types.js";
import { getCompanionBaseUrl, getAuthHeaders } from "../config.js";

function getBase(): string {
...
src/front/providers/companion/upstream/api.ts:import { getCompanionBaseUrl, getAuthHeaders } from "../config.js";
src/front/providers/companion/upstream/ws.ts:import { getCompanionBaseUrl, getCompanionAuthToken } from "../config.js";
```
