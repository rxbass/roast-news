"""Central logging configuration (never use print())."""

import logging
import logging.config


def configure_logging(level: str = "INFO") -> None:
    """Configure root + uvicorn loggers with a single consistent format."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                "uvicorn": {"level": level},
                "uvicorn.error": {"level": level},
                "uvicorn.access": {"level": level},
                # Quiet chatty third-party loggers.
                "httpx": {"level": "WARNING"},
                "openai": {"level": "WARNING"},
                "trafilatura": {"level": "WARNING"},
            },
        }
    )
