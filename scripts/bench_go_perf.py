#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import signal
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import websockets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "ci-artifacts" / "perf-go.json"


@dataclass
class ServerHandle:
    process: subprocess.Popen[str]
    log_path: Path
    port: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark the Go backend and emit perf-go.json.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--port", type=int, default=18120)
    parser.add_argument("--startup-runs", type=int, default=5)
    parser.add_argument("--startup-timeout", type=float, default=10.0)
    parser.add_argument("--health-rps", type=int, default=100)
    parser.add_argument("--health-duration", type=int, default=30)
    parser.add_argument("--memory-requests", type=int, default=100)
    parser.add_argument("--ws-clients", type=int, default=100)
    parser.add_argument("--ws-duration", type=int, default=30)
    parser.add_argument("--ws-interval", type=float, default=1.0)
    return parser.parse_args()


def build_server_binary() -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="boring-ui-go-perf-"))
    binary = tmpdir / "boring-ui-go"
    subprocess.run(
        ["go", "build", "-o", str(binary), "./cmd/server"],
        cwd=ROOT,
        check=True,
    )
    return binary


def server_env(port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "BUI_APP_TOML": str(ROOT / "boring.app.toml"),
            "BORING_HOST": "127.0.0.1",
            "BORING_PORT": str(port),
            "DEV_AUTOLOGIN": "1",
            "AUTH_DEV_USER_ID": "user-1",
            "AUTH_DEV_EMAIL": "owner@example.com",
            "CONTROL_PLANE_PROVIDER": "local",
            "DATABASE_URL": "",
            "SUPABASE_DB_URL": "",
            "SUPABASE_URL": "",
            "SUPABASE_ANON_KEY": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SUPABASE_JWT_SECRET": "",
        }
    )
    return env


def wait_for_health(port: int, timeout: float) -> float:
    deadline = time.perf_counter() + timeout
    url = f"http://127.0.0.1:{port}/health"
    start = time.perf_counter()
    with httpx.Client(timeout=1.0) as client:
        while time.perf_counter() < deadline:
            try:
                response = client.get(url)
                if response.status_code == 200:
                    return (time.perf_counter() - start) * 1000.0
            except httpx.HTTPError:
                pass
            time.sleep(0.02)
    raise TimeoutError(f"/health did not become ready on port {port}")


def start_server(binary: Path, port: int) -> ServerHandle:
    log_file = tempfile.NamedTemporaryFile(prefix="boring-ui-go-perf-", suffix=".log", delete=False)
    log_path = Path(log_file.name)
    log_file.close()
    process = subprocess.Popen(
        [str(binary)],
        cwd=ROOT,
        env=server_env(port),
        stdout=open(log_path, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    return ServerHandle(process=process, log_path=log_path, port=port)


def stop_server(handle: ServerHandle) -> None:
    if handle.process.poll() is not None:
        return
    handle.process.send_signal(signal.SIGTERM)
    try:
        handle.process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        handle.process.kill()
        handle.process.wait(timeout=5)


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * ratio) - 1)
    return ordered[index]


def read_rss_mb(pid: int) -> float:
    status_path = Path(f"/proc/{pid}/status")
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            return int(parts[1]) / 1024.0
    raise RuntimeError(f"VmRSS not found for pid {pid}")


def ensure_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"port {port} is already in use")


async def get_session_cookie(port: int) -> str:
    async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
        response = await client.get(
            f"http://127.0.0.1:{port}/auth/login",
            params={
                "user_id": "user-1",
                "email": "owner@example.com",
                "redirect_uri": "/health",
            },
        )
        if response.status_code not in (200, 302):
            response.raise_for_status()
        cookie = client.cookies.get("boring_session")
        if not cookie:
            raise RuntimeError("login flow did not return boring_session cookie")
        return cookie


async def benchmark_health(port: int, rps: int, duration_seconds: int) -> dict[str, Any]:
    total_requests = rps * duration_seconds
    url = f"http://127.0.0.1:{port}/health"
    latencies: list[float] = []
    errors = 0
    semaphore = asyncio.Semaphore(rps * 2)
    start = time.perf_counter()

    async def worker(index: int, client: httpx.AsyncClient) -> None:
        nonlocal errors
        target = start + (index / rps)
        delay = target - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
        async with semaphore:
            request_start = time.perf_counter()
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    errors += 1
                else:
                    latencies.append((time.perf_counter() - request_start) * 1000.0)
            except httpx.HTTPError:
                errors += 1

    async with httpx.AsyncClient(timeout=5.0) as client:
        await asyncio.gather(*(worker(i, client) for i in range(total_requests)))

    return {
        "requests": total_requests,
        "errors": errors,
        "p50_ms": percentile(latencies, 0.50),
        "p99_ms": percentile(latencies, 0.99),
        "success_rate": 0.0 if total_requests == 0 else (total_requests - errors) / total_requests,
    }


async def benchmark_websocket(port: int, clients: int, duration_seconds: int, interval_seconds: float) -> dict[str, Any]:
    cookie = await get_session_cookie(port)
    cookie_header = {"Cookie": f"boring_session={cookie}"}
    ws_base = f"ws://127.0.0.1:{port}"

    controller = await websockets.connect(f"{ws_base}/ws/pty?provider=shell", additional_headers=cookie_header)
    try:
        first_message = json.loads(await asyncio.wait_for(controller.recv(), timeout=5.0))
        session_id = first_message.get("session_id")
        if first_message.get("type") != "session" or not session_id:
            raise RuntimeError(f"unexpected controller session payload: {first_message}")

        trackers: list[set[str]] = [set()]
        sockets = [controller]
        reader_tasks = []
        stop_event = asyncio.Event()

        async def reader(conn, seen: set[str]) -> None:
            while not stop_event.is_set():
                try:
                    payload = await asyncio.wait_for(conn.recv(), timeout=1.0)
                except TimeoutError:
                    continue
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    return
                try:
                    message = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if message.get("type") != "output":
                    continue
                data = message.get("data") or ""
                for token in data.split():
                    if token.startswith("WSBENCH_"):
                        seen.add(token)

        reader_tasks.append(asyncio.create_task(reader(controller, trackers[0])))

        for _ in range(clients - 1):
            conn = await websockets.connect(f"{ws_base}/ws/pty/{session_id}", additional_headers=cookie_header)
            sockets.append(conn)
            trackers.append(set())
            attached = json.loads(await asyncio.wait_for(conn.recv(), timeout=5.0))
            if attached.get("type") != "session" or attached.get("session_id") != session_id:
                raise RuntimeError(f"unexpected attached session payload: {attached}")
            reader_tasks.append(asyncio.create_task(reader(conn, trackers[-1])))

        await asyncio.sleep(1.0)
        sends = max(1, int(duration_seconds / interval_seconds))
        sent_tokens: list[str] = []
        for index in range(sends):
            token = f"WSBENCH_{index}"
            sent_tokens.append(token)
            await controller.send(json.dumps({"type": "input", "data": f"printf '{token}\\n'\n"}))
            await asyncio.sleep(interval_seconds)

        await asyncio.sleep(1.0)
        stop_event.set()
        for task in reader_tasks:
            task.cancel()
        await asyncio.gather(*reader_tasks, return_exceptions=True)

        expected_messages = len(sent_tokens) * clients
        received_messages = 0
        for seen in trackers:
            for token in sent_tokens:
                if token in seen:
                    received_messages += 1
        message_loss_ratio = 0.0
        if expected_messages:
            message_loss_ratio = 1.0 - (received_messages / expected_messages)

        return {
            "clients": clients,
            "duration_seconds": duration_seconds,
            "sent_messages": len(sent_tokens),
            "expected_messages": expected_messages,
            "received_messages": received_messages,
            "message_loss_ratio": message_loss_ratio,
        }
    finally:
        for conn in locals().get("sockets", []):
            try:
                await conn.close()
            except Exception:
                pass


def run_startup_benchmark(binary: Path, port: int, runs: int, timeout: float) -> dict[str, Any]:
    timings = []
    logs: list[str] = []
    for _ in range(runs):
        ensure_port_free(port)
        handle = start_server(binary, port)
        try:
            timings.append(wait_for_health(port, timeout))
            logs.append(str(handle.log_path))
        finally:
            stop_server(handle)
            ensure_port_free(port)
    return {
        "runs": runs,
        "times_ms": timings,
        "avg_ms": sum(timings) / len(timings),
        "max_ms": max(timings),
        "log_paths": logs,
    }


async def run_main() -> dict[str, Any]:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_port_free(args.port)
    binary = build_server_binary()

    startup = run_startup_benchmark(binary, args.port, args.startup_runs, args.startup_timeout)

    handle = start_server(binary, args.port)
    try:
        wait_for_health(args.port, args.startup_timeout)
        baseline_rss_mb = read_rss_mb(handle.process.pid)

        async with httpx.AsyncClient(timeout=5.0) as client:
            for _ in range(args.memory_requests):
                response = await client.get(f"http://127.0.0.1:{args.port}/health")
                response.raise_for_status()
        post_requests_rss_mb = read_rss_mb(handle.process.pid)

        health = await benchmark_health(args.port, args.health_rps, args.health_duration)
        websocket = await benchmark_websocket(args.port, args.ws_clients, args.ws_duration, args.ws_interval)

        results = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "binary": str(binary),
            "startup": startup,
            "memory": {
                "baseline_rss_mb": baseline_rss_mb,
                "after_requests_rss_mb": post_requests_rss_mb,
            },
            "health_latency": health,
            "websocket": websocket,
            "thresholds": {
                "startup_avg_ms_lt": 500,
                "memory_after_requests_mb_lt": 50,
                "health_p50_ms_lt": 5,
                "health_p99_ms_lt": 30,
                "websocket_message_loss_ratio_lt": 0.01,
            },
            "pass": {
                "startup": startup["avg_ms"] < 500,
                "memory": post_requests_rss_mb < 50,
                "health_p50": health["p50_ms"] < 5,
                "health_p99": health["p99_ms"] < 30,
                "websocket": websocket["message_loss_ratio"] < 0.01,
            },
            "server_log": str(handle.log_path),
        }
        output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        return results
    finally:
        stop_server(handle)


def main() -> None:
    results = asyncio.run(run_main())
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
