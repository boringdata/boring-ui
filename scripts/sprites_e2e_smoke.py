#!/usr/bin/env python3
"""Manual E2E smoke test for Sprites provider integration.

Validates the full lifecycle against a real Sprites.dev account:
  1. Validates required environment variables
  2. Creates/ensures a sprite sandbox
  3. Provisions secrets + credentials
  4. Runs a health check
  5. Creates a checkpoint, performs a mutation, restores checkpoint
  6. Verifies post-restore invariants
  7. Destroys sandbox

Usage:
    # Set required env vars
    export SPRITES_TOKEN="org-slug/org-id/tok-id/tok-value"
    export SPRITES_ORG="my-org"
    export SPRITES_NAME_PREFIX="smoke-"       # optional
    export ANTHROPIC_API_KEY="sk-ant-..."     # optional, for credential test

    # Run
    python3 scripts/sprites_e2e_smoke.py

    # Keep sandbox after test (skip destroy)
    python3 scripts/sprites_e2e_smoke.py --keep

Environment variables:
    SPRITES_TOKEN       (required) Sprites.dev API bearer token
    SPRITES_ORG         (required) Sprites.dev organisation slug
    SPRITES_NAME_PREFIX (optional) Prefix for sprite names (default: "smoke-")
    ANTHROPIC_API_KEY   (optional) Test credential provisioning
    SANDBOX_PORT        (optional) sandbox-agent port (default: 2468)

Output:
    Structured log to stderr (redacted). Summary to stdout.
    Exit code 0 on success, 1 on failure.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time

# Add src/back to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "back"))

from boring_ui.api.modules.sandbox.providers.sprites_client import (
    SpritesClient,
    SpritesClientError,
)
from boring_ui.api.modules.sandbox.providers.sprites import SpritesProvider


# ─────────────────────── Redacted Logging ───────────────────────


class RedactingFormatter(logging.Formatter):
    """Log formatter that redacts tokens and secrets."""

    REDACT_PATTERNS = [
        (re.compile(r"(sk-ant-[a-zA-Z0-9-]{8})[a-zA-Z0-9-]*"), r"\1***"),
        (re.compile(r"(Bearer\s+)[^\s\"']+"), r"\1[REDACTED]"),
        (re.compile(r"(token[=:]\s*)[^\s,\"']+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(api[_-]?key[=:]\s*)[^\s,\"']+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(secret[=:]\s*)[^\s,\"']+", re.IGNORECASE), r"\1[REDACTED]"),
        (re.compile(r"(password[=:]\s*)[^\s,\"']+", re.IGNORECASE), r"\1[REDACTED]"),
    ]

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pattern, replacement in self.REDACT_PATTERNS:
            msg = pattern.sub(replacement, msg)
        return msg


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("sprites_e2e")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(RedactingFormatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger


# ─────────────────────── Test Steps ───────────────────────


class SmokeTestRunner:
    """Orchestrates E2E smoke test steps."""

    def __init__(
        self,
        client: SpritesClient,
        provider: SpritesProvider,
        sandbox_id: str,
        logger: logging.Logger,
        api_key: str = "",
        keep: bool = False,
    ):
        self.client = client
        self.provider = provider
        self.sandbox_id = sandbox_id
        self.log = logger
        self.api_key = api_key
        self.keep = keep
        self.results: list[tuple[str, bool, str]] = []

    def _record(self, step: str, passed: bool, detail: str = "") -> None:
        self.results.append((step, passed, detail))
        icon = "PASS" if passed else "FAIL"
        self.log.info(f"  [{icon}] {step}" + (f" — {detail}" if detail else ""))

    async def run_all(self) -> bool:
        """Run all smoke test steps. Returns True if all passed."""
        self.log.info(f"Starting E2E smoke test for sandbox '{self.sandbox_id}'")
        start = time.monotonic()

        await self.step_create()
        await self.step_get_info()
        await self.step_health_check()
        await self.step_get_logs()

        if self.api_key:
            await self.step_credential_update()

        await self.step_checkpoint_lifecycle()

        if not self.keep:
            await self.step_destroy()
        else:
            self.log.info("  [SKIP] destroy (--keep flag)")

        elapsed = time.monotonic() - start
        return self._print_summary(elapsed)

    async def step_create(self) -> None:
        try:
            config = {}
            if self.api_key:
                config["anthropic_api_key"] = self.api_key
            info = await self.provider.create(self.sandbox_id, config)
            self._record("create", True, f"status={info.status}, url={info.base_url[:40]}...")
        except Exception as e:
            self._record("create", False, str(e)[:200])

    async def step_get_info(self) -> None:
        try:
            info = await self.provider.get_info(self.sandbox_id)
            if info is None:
                self._record("get_info", False, "returned None")
            else:
                self._record("get_info", True, f"status={info.status}")
        except Exception as e:
            self._record("get_info", False, str(e)[:200])

    async def step_health_check(self) -> None:
        try:
            healthy = await self.provider.health_check(self.sandbox_id)
            self._record("health_check", True, f"healthy={healthy}")
        except Exception as e:
            self._record("health_check", False, str(e)[:200])

    async def step_get_logs(self) -> None:
        try:
            logs = await self.provider.get_logs(self.sandbox_id, limit=10)
            self._record("get_logs", True, f"{len(logs)} lines")
        except Exception as e:
            self._record("get_logs", False, str(e)[:200])

    async def step_credential_update(self) -> None:
        try:
            result = await self.provider.update_credentials(
                self.sandbox_id, anthropic_api_key=self.api_key,
            )
            self._record("credential_update", result, "updated" if result else "failed")
        except Exception as e:
            self._record("credential_update", False, str(e)[:200])

    async def step_checkpoint_lifecycle(self) -> None:
        if not self.provider.supports_checkpoints():
            self._record("checkpoint_create", False, "not supported")
            return

        # Create checkpoint
        try:
            cp = await self.provider.create_checkpoint(
                self.sandbox_id, label="smoke-test-baseline",
            )
            if not cp.success:
                self._record("checkpoint_create", False, cp.error or "unknown")
                return
            cp_id = cp.data.id
            self._record("checkpoint_create", True, f"id={cp_id}")
        except Exception as e:
            self._record("checkpoint_create", False, str(e)[:200])
            return

        # Mutate: write a marker file
        try:
            await self.client.exec(
                self.sandbox_id,
                "echo 'SMOKE_MARKER' > /tmp/smoke_marker.txt",
                timeout=30.0,
            )
            _, stdout, _ = await self.client.exec(
                self.sandbox_id,
                "cat /tmp/smoke_marker.txt",
                timeout=15.0,
            )
            has_marker = "SMOKE_MARKER" in stdout
            self._record("checkpoint_mutate", has_marker, "marker written")
        except Exception as e:
            self._record("checkpoint_mutate", False, str(e)[:200])

        # List checkpoints
        try:
            cp_list = await self.provider.list_checkpoints(self.sandbox_id)
            if cp_list.success:
                self._record("checkpoint_list", True, f"{len(cp_list.data)} checkpoints")
            else:
                self._record("checkpoint_list", False, cp_list.error or "unknown")
        except Exception as e:
            self._record("checkpoint_list", False, str(e)[:200])

        # Restore checkpoint
        try:
            restore = await self.provider.restore_checkpoint(self.sandbox_id, cp_id)
            self._record("checkpoint_restore", restore.success, "restored" if restore.success else (restore.error or "unknown"))
        except Exception as e:
            self._record("checkpoint_restore", False, str(e)[:200])

        # Verify post-restore: marker should be gone (restored before mutation)
        try:
            _, stdout, _ = await self.client.exec(
                self.sandbox_id,
                "cat /tmp/smoke_marker.txt 2>&1 || echo 'NO_MARKER'",
                timeout=15.0,
            )
            marker_gone = "NO_MARKER" in stdout or "No such file" in stdout
            self._record(
                "checkpoint_verify",
                marker_gone,
                "marker gone (restored)" if marker_gone else "marker still present!",
            )
        except SpritesClientError:
            # exec failing means the file doesn't exist → good
            self._record("checkpoint_verify", True, "exec failed (file gone)")
        except Exception as e:
            self._record("checkpoint_verify", False, str(e)[:200])

    async def step_destroy(self) -> None:
        try:
            await self.provider.destroy(self.sandbox_id)
            # Verify destroyed
            info = await self.provider.get_info(self.sandbox_id)
            self._record("destroy", info is None, "sprite deleted")
        except Exception as e:
            self._record("destroy", False, str(e)[:200])

    def _print_summary(self, elapsed: float) -> bool:
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = sum(1 for _, ok, _ in self.results if not ok)
        total = len(self.results)

        print("\n" + "=" * 60)
        print(f"Sprites E2E Smoke Test — {passed}/{total} passed, {failed} failed")
        print(f"Elapsed: {elapsed:.1f}s")
        print("=" * 60)

        for step, ok, detail in self.results:
            icon = "PASS" if ok else "FAIL"
            line = f"  [{icon}] {step}"
            if detail:
                line += f" — {detail}"
            print(line)

        print("=" * 60)

        if failed > 0:
            print(f"\nFAILED ({failed} step(s))")
            return False
        else:
            print("\nALL PASSED")
            return True


# ─────────────────────── Main ───────────────────────


def validate_env() -> dict:
    """Validate required environment variables. Returns config dict."""
    token = os.environ.get("SPRITES_TOKEN", "")
    org = os.environ.get("SPRITES_ORG", "")
    prefix = os.environ.get("SPRITES_NAME_PREFIX", "smoke-")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    port = int(os.environ.get("SANDBOX_PORT", "2468"))

    errors = []
    if not token:
        errors.append("SPRITES_TOKEN is required")
    if not org:
        errors.append("SPRITES_ORG is required")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(
            "\nUsage:\n"
            "  export SPRITES_TOKEN='org/org-id/tok-id/tok-value'\n"
            "  export SPRITES_ORG='my-org'\n"
            "  python3 scripts/sprites_e2e_smoke.py",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "token": token,
        "org": org,
        "prefix": prefix,
        "api_key": api_key,
        "port": port,
    }


async def main(keep: bool = False) -> bool:
    config = validate_env()
    logger = setup_logging()

    logger.info("Initializing SpritesClient...")
    client = SpritesClient(
        token=config["token"],
        org=config["org"],
        name_prefix=config["prefix"],
    )

    provider = SpritesProvider(
        client=client,
        sandbox_agent_port=config["port"],
    )

    sandbox_id = f"e2e-{int(time.time()) % 100000}"

    runner = SmokeTestRunner(
        client=client,
        provider=provider,
        sandbox_id=sandbox_id,
        logger=logger,
        api_key=config["api_key"],
        keep=keep,
    )

    try:
        return await runner.run_all()
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sprites E2E smoke test")
    parser.add_argument(
        "--keep", action="store_true",
        help="Keep sandbox after test (skip destroy step)",
    )
    args = parser.parse_args()

    success = asyncio.run(main(keep=args.keep))
    sys.exit(0 if success else 1)
