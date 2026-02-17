#!/usr/bin/env python3
"""Run boring-ui backend with explicit args (avoids shell interpolation)."""
from __future__ import annotations

import argparse

import uvicorn

from boring_ui.api.app import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--include-pty", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-stream", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-approval", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = create_app(
        include_pty=args.include_pty,
        include_stream=args.include_stream,
        include_approval=args.include_approval,
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
