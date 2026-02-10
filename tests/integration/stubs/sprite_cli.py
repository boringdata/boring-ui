#!/usr/bin/env python3
"""Stub ``sprite`` CLI for integration tests.

When invoked as ``sprite exec --org ORG SPRITE_NAME -- COMMAND``,
executes the command in a sandboxed directory (tmp_path from env)
and returns stdout/stderr/exit code.

Supports:
    sprite exec --org <org> <name> -- <command>

Environment variables for test control:
    STUB_SPRITE_WORKDIR  - Directory to chdir into for exec commands.
    STUB_SPRITE_FAIL     - If set, exit with this code and stderr message.
    STUB_SPRITE_DELAY    - Sleep N seconds before responding (simulates latency).
"""
import os
import subprocess
import sys
import time


def main() -> None:
    args = sys.argv[1:]

    # Check for injected failure
    fail_code = os.environ.get("STUB_SPRITE_FAIL")
    if fail_code:
        print(os.environ.get("STUB_SPRITE_FAIL_MSG", "injected CLI failure"), file=sys.stderr)
        sys.exit(int(fail_code))

    # Injected delay
    delay = os.environ.get("STUB_SPRITE_DELAY")
    if delay:
        time.sleep(float(delay))

    if not args or args[0] != "exec":
        print(f"stub sprite: unknown subcommand: {args}", file=sys.stderr)
        sys.exit(1)

    # Parse: exec --org ORG NAME -- COMMAND
    org = None
    name = None
    command = None
    i = 1
    while i < len(args):
        if args[i] == "--org" and i + 1 < len(args):
            org = args[i + 1]
            i += 2
        elif args[i] == "--":
            command = args[i + 1] if i + 1 < len(args) else ""
            break
        elif name is None and not args[i].startswith("-"):
            name = args[i]
            i += 1
        else:
            i += 1

    if command is None:
        print("stub sprite: missing command after --", file=sys.stderr)
        sys.exit(1)

    workdir = os.environ.get("STUB_SPRITE_WORKDIR", "/tmp")

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
