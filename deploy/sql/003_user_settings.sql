-- User settings: simple JSON blob per user, keyed by app_id.
-- Mirrors the workspace_settings pattern but scoped to users.

CREATE TABLE IF NOT EXISTS user_settings (
    user_id    UUID NOT NULL,
    app_id     TEXT NOT NULL DEFAULT 'boring-ui',
    settings   JSONB NOT NULL DEFAULT '{}'::jsonb,
    email      TEXT NOT NULL DEFAULT '',
    display_name TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, app_id)
);
