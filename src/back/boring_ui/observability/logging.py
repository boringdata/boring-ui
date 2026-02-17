"""Structured logging configuration for boring-ui.

Bead: bd-223o.4 (P4)

Configures structlog for JSON-formatted, request-ID-correlated logging
across both the workspace API and control plane.

Usage::

    from boring_ui.observability.logging import configure_logging, get_logger

    configure_logging()  # Call once at app startup
    logger = get_logger()
    logger.info("request_handled", path="/api/tree", status=200)
"""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

import structlog

# Context variable for request-scoped correlation ID.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_configured = False


def _add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Inject the current request_id from context into every log entry."""
    rid = request_id_ctx.get()
    if rid is not None:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(
    *,
    level: str | None = None,
    json_output: bool | None = None,
) -> None:
    """Configure structlog and stdlib logging.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
            Defaults to LOG_LEVEL env var or INFO.
        json_output: If True, emit JSON lines. If False, emit
            human-readable console output. Defaults to LOG_FORMAT
            env var == "json" or True in production.
    """
    global _configured
    if _configured:
        return
    _configured = True

    level = level or os.environ.get("LOG_LEVEL", "INFO")
    if json_output is None:
        json_output = os.environ.get("LOG_FORMAT", "json") == "json"

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy libraries.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given name."""
    return structlog.get_logger(name)
