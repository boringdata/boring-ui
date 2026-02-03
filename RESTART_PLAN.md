# Restart Plan: Kurt-Core UI Import + Composability Refactor

## Goal
Create a generic, composable UI foundation by importing the kurt-core web UI and refactoring it to be easy to integrate and extend, without preserving the current `boring-ui` implementation.

## Source of Truth
`/home/ubuntu/projects/kurt-core/src/kurt/web`

## Step 1: Branch + Remove Current Tool Implementation
- Record current `git status` for traceability.
- Ensure restart branch exists.
- Remove current UI implementation (default scope: `src/` and `public/` only).
- Keep tooling and project scaffolding intact (Vite, tests, lint, configs).

## Step 2: Import Kurt-Core UI + Remove Specifics
- Copy kurt-core client UI (`src/kurt/web/client/src`) into `src/`.
- Map entry point to `src/main` and `src/App` (or equivalents).
- Move/merge static assets into `public/` if needed.
- Remove kurt-core specifics:
- Remove workflow tab and workflow-specific panels/components.
- Remove document endpoints usage (and any related UI).
- Identify any other kurt-core-specific UI/API dependencies and either remove or gate behind adapters.
- Run a minimal smoke check to ensure the app boots.

## Step 3: Make Composable + Extendable
- Extract UI primitives to `src/components/ui/`.
- Organize feature modules into `src/features/*`.
- Introduce a config-driven app shell in `src/config/app.config`.
- Add adapter interfaces for integrations (auth, storage, API, realtime).
- Define public exports for embedding and extension.

## Step 4: Integration + Verification
- Align tooling configs (Vite, Tailwind, TS/JS).
- Update example config(s) to show composable usage.
- Run targeted tests or smoke checks.
- Document integration surface and extension points.

## Kurt-Core Specifics Audit (Initial)
These are currently embedded in the kurt-core client and likely need removal or gating:
- Workflow UI: `WorkflowsPanel`, `WorkflowList`, `WorkflowRow`, `WorkflowTimeline`, `WorkflowMetrics`.
- Workflow panels: `WorkflowTerminalPanel`, `WorkflowDetailPanel`.
- Workflow endpoints: `/api/workflows/*`.
- Review/approval flows: `/api/approval/*` plus `ApprovalPanel`, `ReviewPanel` (keep).
- File system + git endpoints: `/api/tree`, `/api/file`, `/api/git/*`, `/api/search` (keep as optional modules).
- Project/user context: `/api/project`, `/api/me` (may be kept if we want workspace context as a module).

## Assumptions
- We keep tooling and project scaffolding as-is.
- We overwrite `src/` and `public/` completely unless requested otherwise.
- We prioritize composability over preserving existing styling or behavior.

## Open Questions
- Any existing integrations we must preserve (storage keys, config shape)?

## Current State (as of this plan)
- Branch: `restart-from-kurt-core-web`
- `src/` replaced with kurt-core client `src` (imported)
- `public/` removed (no assets imported yet)
- Workflow UI/components/tests removed from `src/` and layout simplified (shell now stands alone).

## Decisions (Confirmed)
- Keep approvals/review flow.
- Keep file tree + git view as optional modules.
- Keep editor (tiptap) as optional module.
- Remove document endpoints and workflow UI (kurt-core specific).
- Local-only mode: remove `/api/me` usage.
- Keep `/api/config`, but allow configurable config path.
