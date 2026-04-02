"""Structured logging setup using structlog.

Provides JSON output for production and colourised console output for
development.  Call ``configure_logging()`` once at application startup.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    json_logs: bool = False,
    request_id: str | None = None,
) -> None:
    """Configure structlog with optional JSON formatting.

    Args:
        level: Logging level string (DEBUG / INFO / WARNING / ERROR / CRITICAL).
        json_logs: When *True* emit newline-delimited JSON; otherwise render
            human-friendly colourised output.
        request_id: Optional correlation ID to bind to every log record.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        # Production: machine-readable JSON
        processors: list[Any] = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so that third-party libraries integrate.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(level.upper()),
    )

    if request_id is not None:
        structlog.contextvars.bind_contextvars(request_id=request_id)


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger for *name*.

    Example::

        log = get_logger(__name__)
        log.info("event", player_id="virat-kohli-ind")
    """
    return structlog.get_logger(name)
