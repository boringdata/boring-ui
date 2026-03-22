#!/usr/bin/env python3
"""Quick health smoke: /health, /api/config, /api/capabilities (no auth needed).

Usage:
    python tests/smoke/smoke_health.py --base-url http://localhost:8000
    python tests/smoke/smoke_health.py --base-url https://julien-hurault--boring-macro-frontend-staging-frontend.modal.run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_lib.client import SmokeClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    client = SmokeClient(args.base_url)

    # Step 1: Health check
    client.set_phase("health")
    resp = client.get("/health", expect_status=(200,))
    if resp.status_code == 200:
        print(f"[smoke] /health OK")
    else:
        print(f"[smoke] /health FAIL: {resp.status_code}")

    # Step 2: App config
    client.set_phase("config")
    resp = client.get("/api/config", expect_status=(200,))
    if resp.status_code == 200:
        cfg = resp.json()
        print(f"[smoke] /api/config: mode={cfg.get('mode', '?')}")
    else:
        print(f"[smoke] /api/config FAIL: {resp.status_code}")

    # Step 3: Capabilities
    client.set_phase("capabilities")
    resp = client.get("/api/capabilities", expect_status=(200,))
    if resp.status_code == 200:
        caps = resp.json()
        features = caps.get("features", {})
        routers = caps.get("routers", [])
        auth = caps.get("auth", {})
        print(f"[smoke] /api/capabilities:")
        print(f"  features: {list(features.keys()) if isinstance(features, dict) else features}")
        print(f"  routers: {routers}")
        print(f"  auth.provider: {auth.get('provider', 'none')}")
    else:
        print(f"[smoke] /api/capabilities FAIL: {resp.status_code}")

    # Step 4: Verify data backend config (catches lightningfs vs http mismatch)
    client.set_phase("data-backend")
    bui_resp = client.get("/__bui/config", expect_status=(200,))
    if bui_resp.status_code == 200:
        bui_cfg = bui_resp.json()
        data_backend = (bui_cfg.get("frontend", {}).get("data", {}).get("backend") or "").lower()
        # Deployed backends with control_plane must use "http" — lightningfs only
        # makes sense for local dev or the standalone Go core mode.
        has_control_plane = isinstance(caps.get("features"), dict) and caps["features"].get("control_plane")
        if has_control_plane and data_backend == "lightningfs":
            client._record("GET", "/__bui/config [data.backend]",
                           bui_resp, False, 0.0,
                           f"data.backend={data_backend} but control_plane=true; should be 'http'")
            print(f"[smoke] FAIL: data.backend=lightningfs with control_plane=true (filetree won't call server)")
        else:
            client._record("GET", "/__bui/config [data.backend]",
                           bui_resp, True, 0.0,
                           f"data.backend={data_backend}")
            print(f"[smoke] data.backend={data_backend} OK")
    else:
        # /__bui/config is optional (Go backend doesn't have it)
        client._record("GET", "/__bui/config [data.backend]",
                       bui_resp, True, 0.0, "endpoint not available (Go backend)")
        print(f"[smoke] /__bui/config not available (Go backend), skipping data.backend check")

    # Report
    report = client.report()
    if args.evidence_out:
        client.write_report(args.evidence_out, extra={"suite": "health"})

    print(json.dumps(report, indent=2))
    if report["ok"]:
        print(f"\nSMOKE HEALTH: ALL {report['total']} STEPS PASSED")
        return 0
    print(f"\nSMOKE HEALTH: {report['failed']}/{report['total']} STEPS FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
