"""Observability infrastructure for boring-ui.

Bead: bd-223o.4 (P4)

Provides structured logging, Prometheus metrics, and request-ID
correlation middleware for both the workspace API and control plane.

Quick start::

    from boring_ui.observability import configure_logging, get_logger
    from boring_ui.observability.middleware import (
        MetricsMiddleware,
        RequestIdMiddleware,
        RequestLoggingMiddleware,
    )
    from boring_ui.observability.metrics import metrics_text

    configure_logging()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)
"""

from .logging import configure_logging, get_logger, request_id_ctx
from .metrics import metrics_text

__all__ = [
    "configure_logging",
    "get_logger",
    "metrics_text",
    "request_id_ctx",
]
