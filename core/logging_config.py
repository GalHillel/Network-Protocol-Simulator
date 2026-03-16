"""
Centralized Logging Configuration

Provides a unified logger factory so all protocol modules use consistent
formatting, levels, and output destinations.
"""

import logging
import sys
from typing import Optional


_CONFIGURED: bool = False


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Create or retrieve a named logger with consistent formatting.

    Args:
        name: Logger name, typically the module or protocol name.
        level: Logging level (default: INFO).
        log_file: Optional file path to write logs to.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    global _CONFIGURED

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)-14s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent log propagation to root to avoid duplicate messages
    logger.propagate = False

    if not _CONFIGURED:
        # Suppress noisy third-party loggers
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        _CONFIGURED = True

    return logger
