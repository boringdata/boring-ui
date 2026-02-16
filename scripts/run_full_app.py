#!/usr/bin/env python3
"""Run boring-ui backend + frontend from a single TOML config.

Usage:
  python3 scripts/run_full_app.py --config app.full.toml

This script overwrites app.config.js from the [ui] table in the TOML.
"""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def js_serialize(obj, indent=2):
    # Minimal JS serializer for TOML -> app.config.js
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        return "\"" + obj.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    if isinstance(obj, list):
        inner = ", ".join(js_serialize(v, indent) for v in obj)
        return f"[{inner}]"
    if isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            key = k if k.isidentifier() else js_serialize(k)
            items.append(f"{key}: {js_serialize(v, indent)}")
        inner = ",\n".join(" " * indent + line for line in items)
        return "{\n" + inner + "\n}"
    raise TypeError(f"Unsupported type for JS serialization: {type(obj)}")


def write_app_config(path: Path, ui_cfg: dict):
    contents = "export default " + js_serialize(ui_cfg) + "\n"
    path.write_text(contents, encoding="utf-8")

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="app.full.toml")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(config_path)
    server = cfg.get("server", {})
    frontend = cfg.get("frontend", {})
    ui = cfg.get("ui", {})

    # Write frontend app.config.js
    app_config_path = Path("src/front/app.config.js").resolve()
    write_app_config(app_config_path, ui)

    # Backend env
    env = os.environ.copy()
    companion_url = server.get("companion_url") or ""
    if companion_url:
        env["COMPANION_URL"] = companion_url
    cors_origins = server.get("cors_origins")
    if cors_origins:
        env["CORS_ORIGINS"] = ",".join(cors_origins)

    # Build backend command
    include_stream = bool(server.get("include_stream", True))
    include_pty = bool(server.get("include_pty", True))
    include_approval = bool(server.get("include_approval", True))
    host = server.get("host", "0.0.0.0")
    port = int(server.get("port", 8000))

    backend_script = Path(__file__).with_name("run_backend.py")
    backend_cmd = [
        sys.executable,
        str(backend_script),
        "--host",
        host,
        "--port",
        str(port),
        "--include-pty" if include_pty else "--no-include-pty",
        "--include-stream" if include_stream else "--no-include-stream",
        "--include-approval" if include_approval else "--no-include-approval",
    ]

    # Frontend command
    fe_host = frontend.get("host", "0.0.0.0")
    fe_port = int(frontend.get("port", 5173))
    vite_api_url = frontend.get("vite_api_url", f"http://localhost:{port}")
    vite_gateway_url = frontend.get("vite_gateway_url")
    companion_proxy_target = frontend.get("companion_proxy_target")

    fe_env = env.copy()
    fe_env["VITE_API_URL"] = vite_api_url
    if vite_gateway_url:
        fe_env["VITE_GATEWAY_URL"] = vite_gateway_url
    if companion_proxy_target:
        fe_env["VITE_COMPANION_PROXY_TARGET"] = companion_proxy_target

    frontend_cmd = ["npm", "run", "dev", "--", "--host", fe_host, "--port", str(fe_port)]

    procs = []

    def terminate_all(signum, frame):
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, terminate_all)
    signal.signal(signal.SIGTERM, terminate_all)

    print(f"Wrote {app_config_path}")
    print("Starting backend...")
    procs.append(subprocess.Popen(backend_cmd, env=env))
    print("Starting frontend...")
    procs.append(subprocess.Popen(frontend_cmd, env=fe_env))

    # Wait for any process to exit
    exit_code = 0
    try:
        exit_code = procs[0].wait()
    finally:
        terminate_all(None, None)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
