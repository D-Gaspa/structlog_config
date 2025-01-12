"""Factory module for configuring and creating structured loggers.

This module provides the main interface for setting up structured logging with both
file and console outputs. It coordinates the configuration loading and logger setup
process while providing a simple public API.
"""

import logging
import sys
import tomllib
from pathlib import Path

import structlog

from .config import LogConfig
from .handlers import create_console_handler, create_file_handler, create_shared_processors


def configure_logging(config_path: Path | None = None) -> None:
    """Configure structlog and standard library logging.

    This function sets up both structlog and the standard library logging system
    with the specified configuration.
    If no configuration path is provided, it will create a default configuration.

    Args:
        config_path: Optional path to a TOML config file.
                     If None, defaults will be used.
    """
    config = _load_config(config_path)  # Load or create config if needed

    shared_processors = create_shared_processors()

    console_handler = create_console_handler(config.console, shared_processors)
    file_handler = create_file_handler(config.file, shared_processors)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger and existing loggers
    _configure_logging_system(
        level=config.level,
        handlers=[console_handler, file_handler]
    )

    # Log successful configuration
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        config_path=str(config_path) if config_path else "default"
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger instance.

    Creates or retrieves a structured logger with the specified name.
    If no name is provided, returns the root logger.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    return structlog.get_logger(name)


def _load_config(config_path: Path | None) -> LogConfig:
    """Load or create logging configuration.

    Args:
        config_path: Optional path to the configuration file

    Returns:
        Loaded or default LogConfig instance
    """
    if config_path is None:
        return _create_default_config()

    try:
        return LogConfig.from_toml(config_path)

    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Error loading logging configuration: {e}. Using defaults.", file=sys.stderr)
        return _create_default_config()


def _create_default_config() -> LogConfig:
    """Create default logging configuration.

    Returns:
        Default LogConfig instance
    """
    root_dir = Path.cwd()
    log_dir = root_dir / "logs"
    return LogConfig.create_default(log_dir)


def _configure_logging_system(level: str, handlers: list[logging.Handler]) -> None:
    """Configure the logging system with the specified handlers.

    Sets up both the root logger and any existing loggers with the provided
    configuration.

    Args:
        level: Logging level to set
        handlers: List of handlers to add to loggers
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Configure existing loggers
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if not isinstance(logger, logging.Logger) or logger_name == "root":
            continue
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(level)
