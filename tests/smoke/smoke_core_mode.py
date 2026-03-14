#!/usr/bin/env python3
"""Core mode E2E smoke test: signup -> signin -> workspace -> files -> agent."""

from __future__ import annotations

import argparse
import json
import sys
import time

# Add scripts dir to path for smoke_lib import
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_lib.auth import random_password, signup_flow, signin_flow
from smoke_lib.client import SmokeClient, StepResult
from smoke_lib.files import check_file_tree, create_and_read_file
from smoke_lib.secrets import supabase_url, supabase_anon_key, resend_api_key
from smoke_lib.workspace import create_workspace, list_workspaces


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--recipient", help="Override test email address")
    parser.add_argument("--timeout", type=int, default=180, help="Resend polling timeout seconds")
    parser.add_argument("--skip-signup", action="store_true", help="Skip signup, use --email/--password")
    parser.add_argument("--email", help="Existing account email (with --skip-signup)")
    parser.add_argument("--password", help="Existing account password (with --skip-signup)")
    parser.add_argument("--skip-agent", action="store_true", help="Skip agent WebSocket test")
    args = parser.parse_args()

    client = SmokeClient(args.base_url)
    sb_url = supabase_url()
    sb_anon = supabase_anon_key()

    if args.skip_signup:
        if not args.email or not args.password:
            print("--skip-signup requires --email and --password", file=sys.stderr)
            return 1
        email = args.email
        password = args.password
    else:
        email = args.recipient or f"qa+smoke-core-{int(time.time())}@boringdata.io"
        password = random_password()
        resend_key = resend_api_key()

        # Phase 1-2: Signup + email confirm
        signup_flow(
            client,
            supabase_url=sb_url,
            supabase_anon_key=sb_anon,
            resend_api_key=resend_key,
            email=email,
            password=password,
            timeout_seconds=args.timeout,
        )

    # Phase 3-4: Signin + session check
    signin_flow(
        client,
        supabase_url=sb_url,
        supabase_anon_key=sb_anon,
        email=email,
        password=password,
    )

    # Phase 5: Create workspace
    ts = int(time.time())
    ws_data = create_workspace(client, name=f"smoke-core-{ts}")
    ws = ws_data.get("workspace") or ws_data
    workspace_id = ws.get("workspace_id") or ws.get("id")

    # Phase 6: List workspaces
    list_workspaces(client, expect_id=workspace_id)

    # Phase 7: File tree
    check_file_tree(client)

    # Phase 8-9: Create + read file
    create_and_read_file(client, path="smoke-test.txt", content=f"smoke-core-{ts}")

    # Phase 10: Agent WebSocket
    if not args.skip_agent:
        from smoke_lib.agent import agent_roundtrip
        result = agent_roundtrip(
            args.base_url,
            message="Say exactly: SMOKE_OK",
            timeout_seconds=30.0,
            cookies=dict(client.cookies),
        )
        if not result.get("ok") and not result.get("skipped"):
            client.results.append(
                StepResult(
                    phase="agent",
                    method="WS",
                    path="/ws/agent/normal/stream",
                    status=0,
                    ok=False,
                    elapsed_ms=0,
                    detail=result.get("error", "unknown"),
                )
            )

    # Report
    report = client.report()
    print(json.dumps(report, indent=2))

    if report["ok"]:
        print(f"\nSMOKE CORE: ALL {report['total']} STEPS PASSED")
        return 0
    else:
        print(f"\nSMOKE CORE: {report['failed']}/{report['total']} STEPS FAILED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
