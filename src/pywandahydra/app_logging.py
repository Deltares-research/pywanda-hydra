"""Logging configuration for pywandahydra."""

from __future__ import annotations

import logging
import sys

import coloredlogs

LOGGER_NAME = "pywandahydra"


def _resolve_level(level: str | int) -> int:
    """Resolve user-provided level to logging integer value."""
    if isinstance(level, int):
        return level

    resolved = logging.getLevelName(str(level).upper())
    if isinstance(resolved, int):
        return resolved

    raise ValueError(f"Value {level} is not a valid log level.")


# Verbose, developer-facing format: shows where each message came from.
_DEBUG_FORMAT = "%(asctime)s [%(name)s:%(lineno)d %(funcName)s][%(levelname)s] %(message)s"
# Clean, user-facing format for normal runs.
_DEFAULT_FORMAT = "%(asctime)s %(message)s"


def setup_logging(level: str | int, colors: bool = True) -> None:
    """Configure the package logger without mutating the root logger.

    Uses a verbose format (module, line, function) at DEBUG level for
    developers, and a clean timestamp + message format otherwise.
    """
    log_level = _resolve_level(level)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)
    logger.propagate = False

    # Ensure repeated setup calls do not accumulate handlers.
    logger.handlers.clear()

    fmt = _DEBUG_FORMAT if log_level <= logging.DEBUG else _DEFAULT_FORMAT

    if colors:
        coloredlogs.install(log_level, logger=logger, fmt=fmt)
        return

    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(logging.Formatter(fmt=fmt))
    logger.addHandler(log_handler)
