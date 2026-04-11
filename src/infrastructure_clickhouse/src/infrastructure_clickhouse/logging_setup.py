"""Shared logging bootstrap for operational services.

Console logging remains enabled for local debugging. Loki is optional and only
attached when ``LOKI_URL`` is configured and the dependency is installed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

DEFAULT_LOG_LEVEL = logging.INFO
CONTEXT_FIELDS = (
    "service",
    "module",
    "area",
    "config_name",
    "target_date",
    "run_id",
    "table_name",
    "batch_size",
    "status_code",
    "chunk_start",
    "chunk_end",
    "offset",
    "row_count",
    "batch_count",
    "run_count",
    "response_sets",
    "training_duration_seconds",
    "total_reconciled",
    "total_skipped",
)
_CONSOLE_HANDLER_NAME = "algo-console"
_LOKI_HANDLER_NAME = "algo-loki"


class ContextFormatter(logging.Formatter):
    """Append selected context keys to a normal log line."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        context_parts = []
        for key in CONTEXT_FIELDS:
            value = getattr(record, key, None)
            if value not in (None, ""):
                context_parts.append(f"{key}={value}")
        if not context_parts:
            return message
        return f"{message} | {' '.join(context_parts)}"


class ServiceLoggerAdapter(logging.LoggerAdapter):
    """Inject a service name into each record without overriding caller context."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        for key, value in self.extra.items():
            extra.setdefault(key, value)
        tags = dict(extra.get("tags", {}))
        for key in ("service", *CONTEXT_FIELDS):
            value = extra.get(key)
            if value not in (None, ""):
                tags[key] = value
        if tags:
            extra["tags"] = tags
        return msg, kwargs


def build_log_extra(**kwargs: Any) -> dict[str, Any]:
    """Filter ``None`` and empty-string values from logging context."""
    return {key: value for key, value in kwargs.items() if value not in (None, "")}


def _normalize_loki_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized = url.rstrip("/")
    if normalized.endswith("/loki/api/v1/push"):
        return normalized
    return f"{normalized}/loki/api/v1/push"


def _handler_by_name(
    logger: logging.Logger, handler_name: str
) -> logging.Handler | None:
    for handler in logger.handlers:
        if handler.get_name() == handler_name:
            return handler
    return None


def _configure_console_handler(root_logger: logging.Logger) -> None:
    if _handler_by_name(root_logger, _CONSOLE_HANDLER_NAME) is not None:
        return

    console_handler = logging.StreamHandler()
    console_handler.set_name(_CONSOLE_HANDLER_NAME)
    console_handler.setFormatter(
        ContextFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(console_handler)


def _configure_loki_handler(root_logger: logging.Logger, loki_url: str) -> None:
    if _handler_by_name(root_logger, _LOKI_HANDLER_NAME) is not None:
        return

    try:
        import logging_loki
    except ImportError:
        logging.getLogger(__name__).warning(
            "LOKI_URL is configured but python-logging-loki is unavailable"
        )
        return

    handler = logging_loki.LokiHandler(
        url=loki_url,
        tags={"job": "algo-repo", "application": "algo-repo"},
        version="1",
    )
    handler.set_name(_LOKI_HANDLER_NAME)
    root_logger.addHandler(handler)


def configure_logging(
    *,
    level: int = DEFAULT_LOG_LEVEL,
    loki_url: str | None = None,
) -> logging.Logger:
    """Configure root logging once and return the root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    _configure_console_handler(root_logger)

    normalized_loki_url = _normalize_loki_url(loki_url or os.getenv("LOKI_URL"))
    if normalized_loki_url is not None:
        _configure_loki_handler(root_logger, normalized_loki_url)

    return root_logger


def get_logger(name: str, *, service: str) -> ServiceLoggerAdapter:
    """Return a logger adapter with shared configuration and service context."""
    configure_logging()
    return ServiceLoggerAdapter(logging.getLogger(name), {"service": service})


__all__ = [
    "CONTEXT_FIELDS",
    "ContextFormatter",
    "ServiceLoggerAdapter",
    "build_log_extra",
    "configure_logging",
    "get_logger",
]
