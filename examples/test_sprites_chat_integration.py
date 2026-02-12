#!/usr/bin/env python3
"""
Integration test: Sprites provider + Chat panels working together.

This demonstrates:
1. Starting a Sprites sandbox
2. Querying capabilities (both providers)
3. Making requests to both sandbox and chat
"""

import asyncio
import httpx
import json
import sys
from typing import Any


class SpritesChat:
    """Client for testing Sprites + Chat integration."""

    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url

    async def request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request to backend."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.backend_url}{path}"
                response = await client.request(method, url, json=json_data)
                return {
                    "status": response.status_code,
                    "data": response.json() if response.content else None,
                    "success": response.is_success,
                }
        except Exception as e:
            return {
                "status": 0,
                "error": str(e),
                "success": False,
            }

    async def get_capabilities(self) -> dict[str, Any]:
        """Get available capabilities (chat providers, services)."""
        print("\n📋 Fetching Capabilities...")
        result = await self.request("GET", "/api/capabilities")
        if result["success"]:
            print("✓ Available services:")
            data = result["data"]
            services = data.get("services", {})
            for name, info in services.items():
                print(f"  • {name}: {info.get('protocol', 'unknown')}")
            return data
        else:
            print(f"✗ Error: {result.get('error')}")
            return {}

    async def sandbox_status(self) -> dict[str, Any]:
        """Check sandbox status."""
        print("\n📦 Checking Sandbox Status...")
        result = await self.request("GET", "/api/sandbox/status")
        if result["success"]:
            data = result["data"]
            status = data.get("status", "unknown")
            print(f"✓ Status: {status}")
            if status == "running":
                print(f"  Base URL: {data.get('base_url')}")
                print(f"  Workspace: {data.get('workspace_path')}")
                print(f"  Provider: {data.get('provider')}")
            return data
        else:
            print(f"✗ Not running")
            return {}

    async def sandbox_start(self) -> dict[str, Any]:
        """Start the sandbox (creates a sprite)."""
        print("\n🚀 Starting Sandbox...")
        print("  Creating sprite on Sprites.dev...")
        result = await self.request("POST", "/api/sandbox/start")
        if result["success"]:
            data = result["data"]
            print(f"✓ Sandbox started!")
            print(f"  ID: {data.get('id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  URL: {data.get('base_url')}")
            return data
        else:
            print(f"✗ Failed: {result.get('error')}")
            return {}

    async def sandbox_health(self) -> bool:
        """Check if sandbox-agent is responding."""
        print("\n❤️  Sandbox Health Check...")
        result = await self.request("GET", "/api/sandbox/health")
        if result["success"]:
            healthy = result["data"].get("healthy", False)
            status = "✓ Healthy" if healthy else "✗ Unhealthy"
            print(f"  {status}")
            return healthy
        else:
            print(f"✗ Failed: {result.get('error')}")
            return False

    async def sandbox_logs(self, limit: int = 20) -> list[str]:
        """Get sandbox logs."""
        print(f"\n📜 Sandbox Logs (last {limit} lines)...")
        result = await self.request("GET", f"/api/sandbox/logs?limit={limit}")
        if result["success"]:
            logs = result["data"].get("logs", [])
            if logs:
                for line in logs:
                    print(f"  {line}")
            else:
                print("  (no logs yet)")
            return logs
        else:
            print(f"✗ Failed: {result.get('error')}")
            return []

    async def sandbox_metrics(self) -> dict[str, Any]:
        """Get sandbox metrics."""
        print("\n📊 Sandbox Metrics...")
        result = await self.request("GET", "/api/sandbox/metrics")
        if result["success"]:
            metrics = result["data"]
            print("✓ Metrics collected:")
            # Print a summary
            for key in ["counters", "gauges", "histograms"]:
                if key in metrics:
                    count = len(metrics[key])
                    print(f"  • {key}: {count} items")
            return metrics
        else:
            print(f"✗ Failed: {result.get('error')}")
            return {}

    async def sandbox_stop(self) -> bool:
        """Stop the sandbox."""
        print("\n⏹️  Stopping Sandbox...")
        result = await self.request("POST", "/api/sandbox/stop")
        if result["success"]:
            print("✓ Stopped")
            return True
        else:
            print(f"✗ Failed: {result.get('error')}")
            return False


async def main():
    """Run integration test."""
    print("\n" + "=" * 60)
    print("🚀 Sprites + Chat Integration Test")
    print("=" * 60)

    client = SpritesChat()

    # Step 1: Check if backend is running
    print("\n[1/6] Checking backend...")
    result = await client.request("GET", "/api/sandbox/status")
    if not result["success"]:
        print("❌ Backend is not running!")
        print("   Start it with:")
        print("   python3 examples/sprites_chat_example.py")
        sys.exit(1)
    print("✓ Backend is running")

    # Step 2: Get capabilities
    print("\n[2/6] Checking available providers...")
    capabilities = await client.get_capabilities()
    if not capabilities:
        print("⚠️  No capabilities returned")

    # Step 3: Check current sandbox status
    print("\n[3/6] Checking current sandbox...")
    status = await client.sandbox_status()

    # Step 4: Start sandbox if not running
    if status.get("status") != "running":
        print("\n[4/6] Starting new sandbox...")
        await client.sandbox_start()
        # Wait for it to fully start
        for i in range(5):
            await asyncio.sleep(2)
            if await client.sandbox_health():
                print("✓ Sandbox is responding")
                break
            print(f"  Waiting for sandbox to be ready... ({i+1}/5)")
    else:
        print("\n[4/6] Sandbox already running")

    # Step 5: Get logs and metrics
    print("\n[5/6] Getting logs and metrics...")
    await client.sandbox_logs(limit=10)
    await client.sandbox_metrics()

    # Step 6: Summary
    print("\n[6/6] Summary")
    print("=" * 60)
    final_status = await client.sandbox_status()
    if final_status.get("status") == "running":
        print("✅ Integration test PASSED")
        print(f"\n📌 Sandbox is ready:")
        print(f"   URL:       {final_status.get('base_url')}")
        print(f"   Workspace: {final_status.get('workspace_path')}")
        print(f"\n🌐 Open browser:")
        print(f"   http://localhost:5173?chat=sandbox")
        print(f"\n📡 Or test via API:")
        print(f"   curl {final_status.get('base_url')}/v1/health")
    else:
        print("❌ Integration test FAILED")
        print(f"   Status: {final_status.get('status', 'unknown')}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
