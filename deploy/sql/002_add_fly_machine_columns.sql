-- Migration: Add Fly Machine identity columns to workspaces table
-- Required for: bd-gbqy.6 (Fly.io backend-agent mode)
-- Applied: 2026-03-18 against Neon project long-glade-16936142

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS machine_id TEXT;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS volume_id TEXT;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS fly_region TEXT DEFAULT 'cdg';

CREATE INDEX IF NOT EXISTS idx_workspaces_machine_id
    ON workspaces(machine_id) WHERE machine_id IS NOT NULL;
