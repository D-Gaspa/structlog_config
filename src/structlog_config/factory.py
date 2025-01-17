"""Factory module for configuring and creating structured loggers.

This module provides the main interface for setting up structured logging with both
file and console outputs.
It manages the global logging state and provides a fluent interface for configuration.
"""

import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import structlog
from structlog.stdlib import BoundLogger

from .config import LogConfig
from .handlers import create_console_handler, create_file_handler, create_shared_processors


@dataclass(frozen=True)
class LoggingConfig:
    """Internal configuration state holder."""
    config: LogConfig
    file_path: Optional[Path] = None
    is_configured: bool = False


class ConfigurationState:
    """Manages the global logging configuration state."""

    def __init__(self) -> None:
        """Initialize the configuration state."""
        self._state: LoggingConfig | None = None
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        """Check if logging has been fully configured."""
        return self._state is not None and self._state.is_configured

    def get_config(self) -> LoggingConfig:
        """Get the current configuration state.

        Returns:
            Current logging configuration

        Raises:
            RuntimeError: If logging hasn't been configured yet
        """
        if self._state is None:
            msg = (
                "Logging hasn't been configured. "
                "Call configure_logging() first or use default console-only logging."
            )
            raise RuntimeError(msg)
        return self._state

    def set_config(self, config: LoggingConfig) -> None:
        """Set the configuration state.

        Args:
            config: New logging configuration

        Raises:
            RuntimeError: If logging has already been configured
        """
        with self._lock:
            if self.is_configured():
                msg = (
                    "Logging has already been configured. "
                    "configure_logging() should only be called once."
                )
                raise RuntimeError(msg)
            self._state = config


# Global configuration state
_config_state = ConfigurationState()


class LoggingBuilder:
    """Builder for logging configuration."""

    def __init__(self, config: LogConfig) -> None:
        """Initialize the logging builder.

        Args:
            config: Base logging configuration
        """
        self._config = config
        self._file_path: Optional[Path] = None

    def with_file(self, path: Optional[str | Path] = None) -> "LoggingBuilder":
        """Add file logging with an optional custom path.

        Args:
            path: Optional custom log file path.
                    If not provided, it uses the path from config file or default path.

        Returns:
            Self for method chaining
        """
        if path is not None:
            self._file_path = Path(path)
        else:
            self._file_path = Path()  # Empty path indicates use config/default

        return self

    def build(self) -> None:
        """Build and apply the logging configuration.

        Raises:
            RuntimeError: If logging has already been configured
        """
        config = LoggingConfig(
            config=self._config,
            file_path=self._file_path,
            is_configured=True
        )

        _config_state.set_config(config)
        _configure_logging(config)


def configure_logging(config_path: Optional[str | Path] = None) -> LoggingBuilder:
    """Configure structlog and standard library logging.

    This function sets up the logging system with the specified configuration.
    If no configuration path is provided, it will create a default configuration.

    Args:
        config_path: Optional path to a TOML config file

    Returns:
        LoggingBuilder instance for method chaining

    Raises:
        ValueError:     If the config path is invalid
        RuntimeError:   If logging has already been configured
    """
    if config_path is not None:
        config = LogConfig.from_toml(Path(config_path))
    else:
        config = LogConfig.create_default(Path.cwd() / "logs")

    return LoggingBuilder(config)


def get_logger(name: Optional[str] = None) -> BoundLogger:
    """Get a configured structlog logger instance.

    Creates or retrieves a structured logger with the specified name.
    If logging hasn't been configured yet, returns a console-only logger.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    if not _config_state.is_configured():
        # Set up basic console-only logging if not configured
        _configure_console_only()
        logger = structlog.get_logger(name)
        logger.warning(
            "Using console-only logging as configure_logging() hasn't been called"
        )
        return logger

    return structlog.get_logger(name)


def _configure_console_only() -> None:
    """Configure basic console-only logging."""
    config = LogConfig.create_default(Path.cwd() / "logs")
    shared_processors = create_shared_processors()
    console_handler = create_console_handler(config.console, shared_processors)

    _configure_logging_system(
        level=config.level,
        handlers=[console_handler]
    )


def _configure_logging(config: LoggingConfig) -> None:
    """Configure the logging system with the specified configuration.

    Args:
        config: Logging configuration to apply
    """
    shared_processors = create_shared_processors()
    handlers = [create_console_handler(config.config.console, shared_processors)]

    if config.file_path is not None:
        # File logging is enabled
        file_config = config.config.file
        if not config.file_path.is_absolute():
            # Use the path from config or default
            file_config = replace(
                file_config,
                path=config.config.file.path
            )
        else:
            # Use the explicit path from builder
            file_config = replace(
                file_config,
                path=config.file_path
            )

        handlers.append(create_file_handler(file_config, shared_processors))

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configure_logging_system(
        level=config.config.level,
        handlers=handlers
    )


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
