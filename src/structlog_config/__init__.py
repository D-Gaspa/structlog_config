"""Structured logging configuration with file and console output support.

This package provides a flexible configuration system for structured logging using
structlog and the Python standard library logging. It supports both file and console
outputs with features like log rotation, colored console output, and rich tracebacks.

Key Features:
    - Rotating file output with configurable size and backup count
    - Colored console output with rich tracebacks
    - TOML-based configuration with sensible defaults
    - Structured logging with JSON formatting for file output
    - Exception information with full tracebacks
    - Timestamp formatting with local time

Basic Usage:
    ```python
    from structlog_config import configure_logging, get_logger
    configure_logging()  # Use default configuration
    logger = get_logger(__name__)
    logger.info("Application started", version="1.0.0")
    ```

Configuration:
    The logging configuration can be specified in a TOML file with the following structure (showing defaults):

    ```toml
    [logging]
    level = "INFO"

    [logging.file]
    path = "logs/app.log"
    max_size = 10485760  # 10MB
    backup_count = 5
    encoding = "utf-8"

    [logging.console]
    colors = true
    rich_tracebacks = true
    ```

    The configuration file path can be provided to configure_logging():
    ```python
    configure_logging(Path("config/logging.toml"))
    ```

Notes:
    - Log files are automatically rotated when they reach the configured size
    - Console output includes colors by default (requires 'colorama')
    - Rich tracebacks are enabled by default (requires 'rich')
    - All timestamps are in local time
"""

from .config import LogConfig
from .factory import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger", "LogConfig"]
