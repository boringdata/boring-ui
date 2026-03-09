"""Git repo provisioning for new workspaces.

Called during workspace creation to:
1. Create a private GitHub repo for the workspace
2. Store repo URL + installation_id in workspace_settings (encrypted)
3. Return the repo info for the caller
"""
import logging
import os
import re

from ...config import APIConfig
from .service import GitHubAppService

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert workspace name to a valid GitHub repo name."""
    slug = re.sub(r'[^a-zA-Z0-9\-]', '-', name.lower().strip())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:60] if slug else 'workspace'


async def provision_workspace_repo(
    config: APIConfig,
    pool,
    workspace_id: str,
    workspace_name: str,
) -> dict | None:
    """Create a GitHub repo for a workspace and persist the connection.

    Args:
        config: API config with GitHub App credentials.
        pool: asyncpg connection pool.
        workspace_id: UUID of the workspace.
        workspace_name: Human-readable workspace name.

    Returns:
        dict with repo info (full_name, clone_url) or None if GitHub not configured.
    """
    gh = GitHubAppService(config)
    if not gh.is_configured:
        logger.debug('GitHub App not configured, skipping repo provisioning')
        return None

    # Find the first installation (single-org setup)
    installation_id = gh.get_first_installation_id()
    if installation_id is None:
        logger.warning('GitHub App has no installations, skipping repo provisioning')
        return None

    # Create the repo
    short_id = str(workspace_id).replace('-', '')[:8]
    repo_name = f'boring-ws-{_slugify(workspace_name)}-{short_id}'
    try:
        repo = gh.create_repo(
            installation_id,
            repo_name,
            private=True,
            description=f'Workspace: {workspace_name}',
        )
    except Exception as exc:
        logger.error('Failed to create GitHub repo %s: %s', repo_name, exc)
        return None

    # Store in workspace_settings (encrypted)
    settings_key = config.settings_encryption_key or os.environ.get('BORING_SETTINGS_KEY', '')
    if settings_key and pool:
        import uuid as _uuid
        ws_uuid = _uuid.UUID(str(workspace_id))
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for key, value in [
                        ('github_repo_url', repo['clone_url']),
                        ('github_installation_id', str(installation_id)),
                    ]:
                        await conn.execute(
                            """
                            INSERT INTO workspace_settings (workspace_id, key, value)
                            VALUES ($1, $2, pgp_sym_encrypt($3, $4))
                            ON CONFLICT (workspace_id, key)
                            DO UPDATE SET value = pgp_sym_encrypt($3, $4), updated_at = now()
                            """,
                            ws_uuid, key, value, settings_key,
                        )
        except Exception as exc:
            logger.error('Failed to store repo settings for workspace %s: %s', workspace_id, exc)

    logger.info('Provisioned repo %s for workspace %s', repo['full_name'], workspace_id)
    return {
        'full_name': repo['full_name'],
        'clone_url': repo['clone_url'],
        'installation_id': installation_id,
    }


async def read_workspace_git_settings(pool, workspace_id: str, settings_key: str) -> dict | None:
    """Read github_repo_url and github_installation_id from workspace settings.

    Returns:
        dict with 'repo_url' and 'installation_id', or None if not configured.
    """
    import uuid as _uuid
    try:
        ws_uuid = _uuid.UUID(str(workspace_id))
    except (ValueError, AttributeError):
        return None

    if not pool or not settings_key:
        return None

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT key, pgp_sym_decrypt(value, $2) AS val
                FROM workspace_settings
                WHERE workspace_id = $1 AND key IN ('github_repo_url', 'github_installation_id')
                """,
                ws_uuid, settings_key,
            )
    except Exception:
        return None

    result = {row['key']: row['val'] for row in rows}
    if 'github_repo_url' not in result:
        return None

    return {
        'repo_url': result.get('github_repo_url'),
        'installation_id': int(result['github_installation_id']) if result.get('github_installation_id') else None,
    }
