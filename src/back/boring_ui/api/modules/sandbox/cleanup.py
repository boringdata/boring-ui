"""Orphan sprite cleanup job.

Identifies and optionally deletes sprites that haven't been accessed
recently.  Run as CLI command or scheduled task.

Usage::

    # List orphans (dry-run, default)
    python -m boring_ui.api.modules.sandbox.cleanup --dry-run

    # Delete orphans older than 30 days
    python -m boring_ui.api.modules.sandbox.cleanup --days 30 --delete

    # Only consider sprites with a specific prefix
    python -m boring_ui.api.modules.sandbox.cleanup --prefix prod- --days 7
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .providers.sprites_client import SpritesClient

logger = logging.getLogger(__name__)


async def find_orphans(
    client: SpritesClient,
    max_inactive_days: int = 30,
    prefix: str = "",
) -> list[dict]:
    """Find sprites not accessed within the inactivity window.

    Args:
        client: SpritesClient instance.
        max_inactive_days: Days of inactivity to consider a sprite orphaned.
        prefix: Only consider sprites whose name starts with this prefix.

    Returns:
        List of orphan sprite metadata dicts.
    """
    sprites = await client.list_sprites()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_inactive_days)

    orphans: list[dict] = []
    for sprite in sprites:
        name = sprite.get("name", "")
        if prefix and not name.startswith(prefix):
            continue

        last_active = sprite.get("last_active_at") or sprite.get("created_at")
        if not last_active:
            # No timestamp at all — treat as orphan
            orphans.append(sprite)
            continue

        try:
            active_time = datetime.fromisoformat(
                last_active.replace("Z", "+00:00"),
            )
        except (ValueError, AttributeError):
            orphans.append(sprite)
            continue

        if active_time < cutoff:
            orphans.append(sprite)

    return orphans


async def cleanup_orphans(
    client: SpritesClient,
    max_inactive_days: int = 30,
    prefix: str = "",
    dry_run: bool = True,
) -> dict:
    """Find and optionally delete orphan sprites.

    Args:
        client: SpritesClient instance.
        max_inactive_days: Days of inactivity threshold.
        prefix: Only consider sprites whose name starts with this prefix.
        dry_run: If True, only list orphans (don't delete).

    Returns:
        Summary: ``{found: int, deleted: int, errors: int, names: list[str]}``.
    """
    orphans = await find_orphans(client, max_inactive_days, prefix)

    logger.info(
        "Orphan scan complete",
        extra={
            "operation": "cleanup_scan",
            "count": len(orphans),
            "max_inactive_days": max_inactive_days,
            "prefix": prefix or "(all)",
            "dry_run": dry_run,
        },
    )

    names = [s.get("name", "?") for s in orphans]

    if dry_run:
        for name in names:
            logger.info(
                "Would delete orphan sprite",
                extra={"operation": "cleanup_dry_run", "sprite_name": name},
            )
        return {"found": len(orphans), "deleted": 0, "errors": 0, "names": names}

    deleted = 0
    errors = 0

    for sprite in orphans:
        name = sprite.get("name", "")
        try:
            await client.delete_sprite(name)
            logger.info(
                "Deleted orphan sprite",
                extra={"operation": "cleanup_delete", "sprite_name": name},
            )
            deleted += 1
        except Exception as e:
            logger.error(
                "Failed to delete orphan sprite",
                extra={
                    "operation": "cleanup_delete",
                    "sprite_name": name,
                    "error": str(e)[:200],
                },
            )
            errors += 1

    return {"found": len(orphans), "deleted": deleted, "errors": errors, "names": names}


async def _main() -> None:
    """CLI entry point."""
    import argparse
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Cleanup orphan sprites")
    parser.add_argument(
        "--days", type=int, default=30, help="Max inactive days (default: 30)",
    )
    parser.add_argument(
        "--delete", action="store_true", help="Actually delete (default: dry-run)",
    )
    parser.add_argument(
        "--prefix", default="", help="Sprite name prefix filter",
    )
    args = parser.parse_args()

    token = os.environ.get("SPRITES_TOKEN", "")
    if not token:
        print("Error: SPRITES_TOKEN environment variable required")
        raise SystemExit(1)

    client = SpritesClient(
        token=token,
        org=os.environ.get("SPRITES_ORG", ""),
        name_prefix=os.environ.get("SPRITES_NAME_PREFIX", ""),
    )

    try:
        result = await cleanup_orphans(
            client,
            max_inactive_days=args.days,
            prefix=args.prefix,
            dry_run=not args.delete,
        )
        mode = "DELETE" if args.delete else "DRY-RUN"
        print(f"[{mode}] Found: {result['found']}, Deleted: {result['deleted']}, Errors: {result['errors']}")
        if result["names"]:
            for name in result["names"]:
                print(f"  - {name}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_main())
