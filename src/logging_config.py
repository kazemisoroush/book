"""Structured logging configuration for the audiobook generator.

Call ``configure()`` once at application startup (in ``main.py`` or the
equivalent entry point) before any loggers are used.

All modules obtain their logger with::

    import structlog
    logger = structlog.get_logger(__name__)

Log level is controlled by (in priority order):
1. The ``log_level`` argument to :func:`configure`
2. The ``LOG_LEVEL`` environment variable
3. The default of ``"INFO"``
"""
import logging
import os
from typing import Optional

import structlog


def configure(log_level: Optional[str] = None) -> None:
    """Configure structlog and the stdlib ``logging`` root logger.

    Sets up a shared processor chain so that all structlog loggers
    produce consistent output.  In a TTY context the output is rendered
    as human-readable key=value pairs; in non-TTY contexts (CI, prod)
    output is rendered as JSON.

    Args:
        log_level: One of ``"DEBUG"``, ``"INFO"``, ``"WARNING"``,
                   ``"ERROR"``, ``"CRITICAL"``.  If *None*, the
                   ``LOG_LEVEL`` environment variable is consulted; if
                   that is also absent, ``"INFO"`` is used.
    """
    # Resolve effective log level
    effective_level_str = (
        log_level
        or os.environ.get("LOG_LEVEL")
        or "INFO"
    ).upper()
    effective_level = getattr(logging, effective_level_str, logging.INFO)

    # Configure stdlib root logger
    logging.basicConfig(
        format="%(message)s",
        level=effective_level,
    )
    logging.getLogger().setLevel(effective_level)

    # Shared processors applied to every structlog log entry
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
