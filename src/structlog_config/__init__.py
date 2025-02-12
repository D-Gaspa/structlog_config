"""Structured logging configuration with file and console output support.

This package provides a flexible configuration system for structured logging using
structlog and the Python standard library logging. It supports both file and console
outputs with features like log rotation, colored console output, and rich tracebacks.

Key Features:
    - Thread-safe configuration with single-configuration enforcement
    - Console-only fallback when logging is accessed before configuration
    - Optional rotating file output with configurable size and backup count
    - Colored console output with rich tracebacks (enabled by default)
    - Pattern-based logging level control for specific loggers
    - TOML-based configuration with sensible defaults
    - Structured logging with JSON formatting for file output
    - Exception information with full tracebacks
    - Timestamp formatting with local time

Basic Usage:
    ```python
    from structlog_config import configure_logging, get_logger

    # Console-only logging with defaults (INFO level, colored output)
    logger = get_logger(__name__)
    logger.info("Using default console-only logging")

    # With file output using configuration file
    configure_logging("config/logging.toml").with_file().build()
    logger = get_logger(__name__)
    logger.info("Logging configured with file output")

    # With pattern-based logging levels
    configure_logging().with_pattern_level("sqlalchemy.*", "WARNING").build()
    logger = get_logger("sqlalchemy.engine")
    logger.info("This message will not be logged")

    # Custom file path (it creates directory if needed)
    configure_logging().with_file("logs/custom.log").build()
    logger = get_logger(__name__)
    logger.info("Logging to custom file path")
    ```

Configuration:
    The logging configuration can be specified in a TOML file with the following structure:

    ```toml
    [logging]
    level = "INFO"  # (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    [logging.patterns]
    "sqlalchemy.*" = "WARNING"     # Set all SQLAlchemy loggers to WARNING
    "sqlalchemy.engine.*" = "INFO" # Override engine loggers to INFO

    [logging.file]
    path = "logs/app.log"
    max_size = 10485760  # 10MB
    backup_count = 5
    encoding = "utf-8"

    [logging.console]
    colors = true
    rich_tracebacks = true
    ```

    All sections and fields are optional with sensible defaults.
    File logging must be explicitly enabled using `.with_file()`.

Structured Logging:
    Add context to your logs with structured data:

    ```python
    from structlog_config import get_logger

    logger = get_logger(__name__)

    # Add persistent context
    logger = logger.bind(user_id="123", service="example")

    # Log with additional context
    logger.info(
        "User action completed",
        action="purchase",
        item_id="456",
        amount=29.99
    )

    # Thread/async-safe context
    with structlog.contextvars.bound_contextvars(request_id="abc-123"):
        logger.info("Processing request")
    ```

Implementation Notes:
    - Log files are automatically rotated when they reach the configured size
    - Console output includes colors by default (requires 'colorama')
    - Rich tracebacks are enabled by default (requires 'rich')
    - All timestamps are in local time
    - File logging requires write permissions for the target directory
    - Configuration is thread-safe and can only be fully configured once
    - Early logging access before configuration uses console-only output
    - Pattern-based levels follow glob-style matching (e.g., "app.*")
    - TOML pattern configurations take precedence over builder methods
"""

from .config import LogConfig
from .factory import configure_logging, get_logger

__all__ = ["LogConfig", "configure_logging", "get_logger"]
