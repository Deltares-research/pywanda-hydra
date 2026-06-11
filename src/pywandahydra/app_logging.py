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


def setup_logging(level: str | int, colors: bool = True) -> None:
    """Configure the package logger without mutating the root logger."""
    log_level = _resolve_level(level)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)
    logger.propagate = False

    # Ensure repeated setup calls do not accumulate handlers.
    logger.handlers.clear()

    if colors:
        coloredlogs.install(log_level, logger=logger)
        return

    log_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(threadName)s][%(filename)s:%(lineno)d][%(levelname)s]: %(message)s"
    )
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
