import logging
import logging.config
import sys
from typing import Any

import structlog

from core.settings import settings


def setup_logging() -> None:
    log_level = "DEBUG" if settings.DEBUG_MODE else "INFO"

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
                "foreign_pre_chain": processors,
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(),
                "foreign_pre_chain": processors,
            },
        },
        "handlers": {
            "default": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "console" if settings.DEBUG_MODE else "json",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {"handlers": ["default"], "level": log_level, "propagate": True},
            "uvicorn": {"handlers": ["default"], "level": log_level, "propagate": False},
            "sqlalchemy.engine": {"handlers": ["default"], "level": log_level, "propagate": False},
            "saga": {"handlers": ["default"], "level": log_level, "propagate": False},
        },
    }

    logging.config.dictConfig(logging_config)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
