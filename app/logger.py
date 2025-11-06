"""
logger.py
---------

This module configures the application logger using structlog and colorlog.

- In development and testing environments, it sets up a colored log formatter
  for improved readability in the console.
- In staging and production environments, it switches to JSON logging for
  better integration with log aggregation tools.
- Provides a `logger` instance for use throughout the application.

Usage:
    from app.logger import logger
    logger.info("Your log message", extra_field="value")
"""

import os
import logging
import colorlog
import structlog

# Detect environment
env = os.environ.get("FLASK_ENV", "development").lower()

# Configure the root logger with colorlog for human-readable output
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d "
        "%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
)

# Set log level from LOG_LEVEL env var, default to INFO
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    log_level = "INFO"
logging.basicConfig(level=getattr(logging, log_level), handlers=[handler])

# Choose renderer based on environment
if env in ("development", "testing"):
    renderer = structlog.dev.ConsoleRenderer(colors=True)
else:
    renderer = structlog.processors.JSONRenderer()

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        renderer,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
