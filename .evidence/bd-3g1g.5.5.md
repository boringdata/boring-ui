# Evidence: bd-3g1g.5.5

*2026-02-18T09:16:36Z by Showboat 0.5.0*

Updated top-level docs that described legacy file/git/pty endpoints as if they were current, aligning them to canonical surfaces (primarily /api/v1/files/*, /api/v1/git/*, /ws/pty).

```bash
rg -n '\b/api/git\b|/api/git/|/ws/pty/\{|/api/tree\b|/api/file\b|/api/search\b' -S README.md docs/PLAN.md docs/PLAN_ENHANCEMENTS.md || true
```

```output
```

```bash
rg -n '/api/v1/files/|/api/v1/git/|/ws/pty\b' -S README.md docs/PLAN.md docs/PLAN_ENHANCEMENTS.md | LC_ALL=C sort
```

```output
README.md:281:| pty              | /ws/pty  | Shell terminal WebSocket       |
README.md:363:| /api/v1/files/list    | GET    | List directory entries           |
README.md:364:| /api/v1/files/read    | GET    | Read file content                |
README.md:365:| /api/v1/files/write   | PUT    | Write file content               |
README.md:366:| /api/v1/files/delete  | DELETE | Delete file                      |
README.md:367:| /api/v1/files/rename  | POST   | Rename file                      |
README.md:368:| /api/v1/files/move    | POST   | Move file                        |
README.md:369:| /api/v1/files/search  | GET    | Search files                     |
README.md:370:| /api/v1/git/status    | GET    | Git status                       |
README.md:371:| /api/v1/git/diff      | GET    | Git diff                         |
README.md:372:| /api/v1/git/show      | GET    | Git show                         |
README.md:373:| /ws/pty               | WS     | Shell PTY (query params include `session_id`, `provider`) |
docs/PLAN.md:207:- Files API: `GET /api/v1/files/list`, `GET /api/v1/files/read`, `PUT /api/v1/files/write`, `DELETE /api/v1/files/delete`, `POST /api/v1/files/rename`, `POST /api/v1/files/move`, `GET /api/v1/files/search`.
docs/PLAN.md:208:- Git API: `GET /api/v1/git/status`, `GET /api/v1/git/diff`, `GET /api/v1/git/show`.
docs/PLAN.md:209:- PTY API: `WS /ws/pty?session_id=<id>&provider=<name>`.
docs/PLAN_ENHANCEMENTS.md:60:  - `GET /api/v1/files/list?path=.` list directory entries.
docs/PLAN_ENHANCEMENTS.md:61:+- `GET /api/v1/files/list?path=.&depth=1&limit=500&cursor=<id>` for pagination.
docs/PLAN_ENHANCEMENTS.md:62:+- `GET /api/v1/files/list?includeHidden=false&respectGitignore=true` for safe defaults.
docs/PLAN_ENHANCEMENTS.md:64: - `GET /api/v1/files/read?path=...` read file content.
docs/PLAN_ENHANCEMENTS.md:65:+- `HEAD /api/v1/files/read?path=...` return metadata only.
docs/PLAN_ENHANCEMENTS.md:66:+- `GET /api/v1/files/read?path=...` returns `etag` and `lastModified`.
docs/PLAN_ENHANCEMENTS.md:68: - `PUT /api/v1/files/write?path=...` write file content with `{ content }`.
docs/PLAN_ENHANCEMENTS.md:69: - `DELETE /api/v1/files/delete?path=...` delete file.
docs/PLAN_ENHANCEMENTS.md:70: - `POST /api/v1/files/rename` with `{ old_path, new_path }`.
docs/PLAN_ENHANCEMENTS.md:71: - `POST /api/v1/files/move` with `{ src_path, dest_dir }`.
docs/PLAN_ENHANCEMENTS.md:72:  - `GET /api/v1/files/search?q=pattern&path=.` glob-style filename search.
docs/PLAN_ENHANCEMENTS.md:73:+- `GET /api/v1/files/search?mode=content&limit=200&cursor=<id>` for content search.
docs/PLAN_ENHANCEMENTS.md:74:+- `POST /api/v1/files/batch` to read multiple files in one request.
docs/PLAN_ENHANCEMENTS.md:86: - `WS /ws/pty?session_id=<id>&provider=<name>` for terminal sessions.
```

```bash
git show --name-only --pretty=format: 9f6ddbc -- README.md docs/PLAN.md docs/PLAN_ENHANCEMENTS.md .beads/issues.jsonl | LC_ALL=C sort
```

```output
.beads/issues.jsonl
README.md
docs/PLAN.md
docs/PLAN_ENHANCEMENTS.md
```
