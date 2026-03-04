#!/usr/bin/env python3
"""Run boring-ui services from a single TOML config.

Usage:
  python3 scripts/run_full_app.py --config app.full.toml

This script overwrites app.config.js from the [ui] table in the TOML and can
launch companion/pi services in addition to backend/frontend.
"""
import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

DEPLOY_MODE_CORE = "core"
DEPLOY_MODE_SANDBOX_PROXY = "sandbox-proxy"


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


def _parse_command(value, default_cmd):
    if value is None:
        return list(default_cmd)
    if isinstance(value, str):
        cmd = shlex.split(value)
        return cmd or list(default_cmd)
    if isinstance(value, (list, tuple)):
        cmd = [str(part) for part in value if str(part).strip()]
        return cmd or list(default_cmd)
    raise TypeError(f"Unsupported command type: {type(value)}")


def _port_from_url(url: str | None, default: int) -> int:
    if not url:
        return default
    try:
        parsed = urlparse(url)
        if parsed.port:
            return int(parsed.port)
    except Exception:
        return default
    return default


def _apply_extra_env(base_env: dict, extra: dict | None) -> dict:
    if not extra:
        return base_env
    env = base_env.copy()
    for key, value in extra.items():
        env[str(key)] = str(value)
    return env


def _normalize_deploy_mode(raw_mode: str | None) -> str:
    value = str(raw_mode or "").strip().lower()
    if value in {"", DEPLOY_MODE_CORE, "direct"}:
        return DEPLOY_MODE_CORE
    if value in {
        DEPLOY_MODE_SANDBOX_PROXY,
        "sandbox_proxy",
        "sandbox-proxy",
        "proxy",
        "sandbox",
    }:
        return DEPLOY_MODE_SANDBOX_PROXY
    raise ValueError(
        f"Unsupported deploy mode '{raw_mode}'. Use '{DEPLOY_MODE_CORE}' or '{DEPLOY_MODE_SANDBOX_PROXY}'."
    )


def _resolve_deploy_mode(
    *,
    cli_mode: str | None,
    cli_proxy_url: str | None,
    cfg: dict,
    env: dict[str, str],
) -> tuple[str, str | None]:
    deployment_cfg = cfg.get("deployment", {})
    deploy_mode = _normalize_deploy_mode(
        cli_mode
        or env.get("DEPLOY_MODE")
        or deployment_cfg.get("mode")
        or DEPLOY_MODE_CORE
    )
    proxy_url = (
        cli_proxy_url
        or env.get("SANDBOX_PROXY_URL")
        or deployment_cfg.get("sandbox_proxy_url")
        or cfg.get("frontend", {}).get("vite_gateway_url")
    )
    if proxy_url:
        proxy_url = str(proxy_url).strip().rstrip("/")
    return deploy_mode, proxy_url


def _resolve_frontend_env(
    *,
    base_env: dict[str, str],
    frontend_cfg: dict,
    deploy_mode: str,
    sandbox_proxy_url: str | None,
    backend_port: int,
) -> dict[str, str]:
    fe_env = base_env.copy()
    vite_api_url = frontend_cfg.get("vite_api_url", f"http://localhost:{backend_port}")
    companion_proxy_target = frontend_cfg.get("companion_proxy_target")

    if deploy_mode == DEPLOY_MODE_SANDBOX_PROXY:
        gateway_url = sandbox_proxy_url or "http://127.0.0.1:8080"
        fe_env["VITE_API_URL"] = gateway_url
        fe_env["VITE_GATEWAY_URL"] = gateway_url
    else:
        fe_env["VITE_API_URL"] = vite_api_url
        configured_gateway = frontend_cfg.get("vite_gateway_url")
        if configured_gateway:
            fe_env["VITE_GATEWAY_URL"] = str(configured_gateway).strip().rstrip("/")
        else:
            fe_env.pop("VITE_GATEWAY_URL", None)

    if companion_proxy_target:
        fe_env["VITE_COMPANION_PROXY_TARGET"] = companion_proxy_target
    else:
        fe_env.pop("VITE_COMPANION_PROXY_TARGET", None)
    return fe_env


def _start_process(name: str, cmd: list[str], env: dict, procs: list[tuple[str, subprocess.Popen]]):
    print(f"Starting {name}: {' '.join(cmd)}")
    # Start each service in its own process group so shutdown can reliably
    # terminate npm wrappers and their child processes.
    proc = subprocess.Popen(cmd, env=env, start_new_session=True)
    procs.append((name, proc))


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="app.full.toml")
    parser.add_argument(
        "--deploy-mode",
        choices=[DEPLOY_MODE_CORE, DEPLOY_MODE_SANDBOX_PROXY],
        default=None,
        help="Deployment mode override (default: DEPLOY_MODE env, [deployment].mode, else core).",
    )
    parser.add_argument(
        "--sandbox-proxy-url",
        default=None,
        help="Sandbox proxy base URL for sandbox-proxy mode (default: SANDBOX_PROXY_URL env or config).",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(config_path)
    server = cfg.get("server", {})
    frontend = cfg.get("frontend", {})
    services = cfg.get("services", {})
    ui = cfg.get("ui", {})
    deploy_mode, sandbox_proxy_url = _resolve_deploy_mode(
        cli_mode=args.deploy_mode,
        cli_proxy_url=args.sandbox_proxy_url,
        cfg=cfg,
        env=os.environ,
    )
    companion_service = services.get("companion", {})
    pi_service = services.get("pi", {})

    # Write frontend app.config.js
    app_config_path = Path("src/front/app.config.js").resolve()
    write_app_config(app_config_path, ui)

    # Backend env
    env = os.environ.copy()
    env["DEPLOY_MODE"] = deploy_mode
    if sandbox_proxy_url:
        env["SANDBOX_PROXY_URL"] = sandbox_proxy_url
    companion_enabled = bool(companion_service.get("enabled", False))
    companion_port = int(companion_service.get("port") or _port_from_url(server.get("companion_url"), 3456))
    companion_url = server.get("companion_url") or companion_service.get("url")
    if not companion_url and companion_enabled:
        companion_url = f"http://localhost:{companion_port}"

    pi_enabled = bool(pi_service.get("enabled", False))
    pi_port = int(pi_service.get("port") or _port_from_url(server.get("pi_url"), 8789))
    pi_url = server.get("pi_url") or pi_service.get("url")
    if not pi_url and pi_enabled:
        pi_url = f"http://localhost:{pi_port}"
    pi_mode = str(server.get("pi_mode") or pi_service.get("mode") or "backend")

    if companion_url:
        env["COMPANION_URL"] = companion_url
    if pi_url:
        env["PI_URL"] = pi_url
        env["PI_MODE"] = pi_mode
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
    fe_env = _resolve_frontend_env(
        base_env=env,
        frontend_cfg=frontend,
        deploy_mode=deploy_mode,
        sandbox_proxy_url=sandbox_proxy_url,
        backend_port=port,
    )

    frontend_cmd = ["npm", "run", "dev", "--", "--host", fe_host, "--port", str(fe_port)]

    procs: list[tuple[str, subprocess.Popen]] = []

    def terminate_all(exit_code: int = 0):
        for _, p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for _, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        return exit_code

    def signal_handler(signum, frame):
        raise SystemExit(terminate_all(0))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Wrote {app_config_path}")
    print(f"Deployment mode: {deploy_mode}")
    if deploy_mode == DEPLOY_MODE_SANDBOX_PROXY:
        print(f"Sandbox proxy URL: {fe_env['VITE_API_URL']}")
    else:
        print(f"Backend API URL: {fe_env['VITE_API_URL']}")

    try:
        if companion_enabled:
            companion_cmd = _parse_command(
                companion_service.get("command"),
                ["npm", "run", "companion:service"],
            )
            companion_env = env.copy()
            companion_env["PORT"] = str(companion_port)
            companion_env = _apply_extra_env(companion_env, companion_service.get("env"))
            _start_process("companion", companion_cmd, companion_env, procs)

        if pi_enabled:
            pi_cmd = _parse_command(
                pi_service.get("command"),
                ["npm", "run", "pi:service"],
            )
            pi_env = env.copy()
            pi_env["PI_SERVICE_HOST"] = str(pi_service.get("host", "0.0.0.0"))
            pi_env["PI_SERVICE_PORT"] = str(pi_port)
            pi_env["PI_SERVICE_CORS_ORIGIN"] = str(pi_service.get("cors_origin", "*"))
            pi_env = _apply_extra_env(pi_env, pi_service.get("env"))
            _start_process("pi", pi_cmd, pi_env, procs)

        _start_process("backend", backend_cmd, env, procs)
        _start_process("frontend", frontend_cmd, fe_env, procs)

        while True:
            for name, proc in procs:
                code = proc.poll()
                if code is not None:
                    if code != 0:
                        print(f"{name} exited with code {code}", file=sys.stderr)
                    return terminate_all(code)
            time.sleep(0.5)
    finally:
        terminate_all(0)


if __name__ == "__main__":
    raise SystemExit(run())
