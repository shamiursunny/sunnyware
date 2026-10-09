# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Structured logging with stderr fallback."""

import logging
import sys
from pathlib import Path
import structlog


def configure_logging(log_dir: str = None):
    """Configure structlog. Falls back to stderr if file logging fails."""
    if log_dir is None:
        try:
            from . import paths
            log_dir = str(paths.logs_dir())
        except Exception:
            log_dir = "./data/logs"
    file_handler = None
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        log_file = Path(log_dir) / "sunnyware.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
    except Exception:
        file_handler = None

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler if file_handler else logging.StreamHandler(sys.stderr))

    return structlog.get_logger("sunnyware")