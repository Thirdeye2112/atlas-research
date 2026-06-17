"""
Structured logging — moved from atlas_research/logging.py.
No logic changes; only the import path changes.

Usage:
    from atlas_research.utils.logging import get_logger
    log = get_logger(__name__)
    log.info("pipeline.started", date="2026-06-06", tickers=185)
"""

from __future__ import annotations

import io
import logging
import sys

import structlog


def _utf8_stream(stream):
    """
    Return a UTF-8 stream wrapping ``stream`` so log records never raise
    UnicodeEncodeError on a non-UTF-8 console (Windows cp1252).

    Prefers in-place reconfigure (Python 3.7+ TextIOWrapper.reconfigure);
    falls back to wrapping the underlying buffer; returns the stream
    unchanged if neither is possible.
    """
    # Already UTF-8 — nothing to do.
    if getattr(stream, "encoding", "").lower().replace("-", "") == "utf8":
        return stream
    try:
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        return stream
    except (AttributeError, ValueError):
        pass
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return io.TextIOWrapper(
            buffer, encoding="utf-8", errors="backslashreplace",
            line_buffering=True,
        )
    return stream


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """
    Configure structlog for the process.
    Call once at process startup (done in each script entry point).

    Args:
        level: Python log level string.
        fmt:   'console' for human-readable; 'json' for production.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Force UTF-8 on the console stream.  On Windows the default stdout
    # encoding is cp1252, which raises UnicodeEncodeError whenever a log
    # record contains a non-Latin-1 character (e.g. a real "→" U+2192 in a
    # message or exception).  Python's logging module swallows that handler
    # error, so the offending record — including wf.fold_complete metrics —
    # is SILENTLY DROPPED from the console.  Reconfiguring to UTF-8 with a
    # backslashreplace fallback guarantees every record is emitted.
    stream = _utf8_stream(sys.stdout)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    for noisy in ("yfinance", "urllib3", "apscheduler", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
