"""Factory module for configuring and creating structured loggers.

This module provides the main interface for setting up structured logging with both file and console outputs.
It manages the global logging state and provides a fluent interface for configuration.

The module enforces a single-configuration pattern where logging can only be fully configured once.
However, if logging is accessed before configuration, it provides a console-only fallback.
"""

import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import structlog
from structlog.stdlib import BoundLogger

from .config import FileHandlerConfig, LogConfig
from .handlers import create_console_handler, create_file_handler, create_shared_processors


@dataclass(frozen=True)
class LoggingConfig:
    """Internal configuration state holder.

    This class maintains the complete logging configuration state including both
    the base configuration and file-specific settings.

    Attributes:
        config:         Base logging configuration from TOML or defaults
        file_path:      Optional custom path for file logging
        is_configured:  Flag indicating if logging has been fully configured
    """

    config: LogConfig
    file_path: Path | None = None
    is_configured: bool = False


class ConfigurationState:
    """Manages the global logging configuration state.

    This class provides thread-safe access to the global logging configuration
    and ensures that logging can only be fully configured once.

    Attributes:
        _state: Current logging configuration state
        _lock:  Threading lock for thread-safe state modifications
    """

    def __init__(self) -> None:
        """Initialize the configuration state."""
        self._state: LoggingConfig | None = None
        self._lock: Final = threading.Lock()

    def is_configured(self) -> bool:
        """Check if logging has been fully configured.

        Returns:
            True if logging has been configured, False otherwise
        """
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
            config: New logging configuration to apply

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
_config_state: Final = ConfigurationState()


class LoggingBuilder:
    """Builder for logging configuration.

    Provides a fluent interface for configuring logging settings, including
    optional file logging with custom paths.

    Attributes:
        _config:    Base logging configuration from TOML or defaults
        _file_path: Optional custom path for file logging output
    """

    def __init__(self, config: LogConfig) -> None:
        """Initialize the logging builder.

        Args:
            config: Base logging configuration
        """
        self._config: Final = config
        self._file_path: Path | None = None

    def with_file(self, path: str | Path | None = None) -> "LoggingBuilder":
        """Add file logging with an optional custom path.

        If a path is provided, it can be either relative or absolute.
        Relative paths are resolved from the current working directory.
        If no path is provided, the path from the configuration file or default path is used.

        Args:
            path: Optional custom log file path

        Returns:
            Self for method chaining
        """
        if path is not None:
            self._file_path = Path(path)

        return self

    def build(self) -> None:
        """Build and apply the logging configuration.

        This method finalizes the configuration and sets up the logging system.
        It can only be called once per application lifecycle.
        """
        config = LoggingConfig(
            config=self._config,
            file_path=self._file_path,
            is_configured=True
        )

        _config_state.set_config(config)
        _configure_logging(config)


def configure_logging(config_path: str | Path | None = None) -> LoggingBuilder:
    """Configure structlog and standard library logging.

    This function initiates the logging setup process.
    If no configuration path is provided, it creates a default configuration.
    The returned builder allows further customization before finalizing the configuration.

    Args:
        config_path: Optional path to a TOML config file

    Returns:
        LoggingBuilder instance for method chaining
    """
    if config_path is not None:
        config = LogConfig.from_toml(Path(config_path))
    else:
        config = LogConfig.create_default(Path.cwd() / "logs")

    return LoggingBuilder(config)


def get_logger(name: str | None = None) -> BoundLogger:
    """Get a configured structlog logger instance.

    Creates or retrieves a structured logger with the specified name.
    If logging hasn't been configured yet, returns a console-only logger and issues a warning.

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
    """Configure basic console-only logging.

    Sets up a minimal logging configuration that only outputs to the console.
    This is used as a fallback when logging is accessed before configuration.
    """
    config = LogConfig.create_default(Path.cwd() / "logs")
    shared_processors = create_shared_processors()
    console_handler = create_console_handler(config.console, shared_processors)

    _configure_logging_system(
        level=config.level,
        handlers=[console_handler]
    )


def _configure_logging(config: LoggingConfig) -> None:
    """Configure the logging system with the specified configuration.

    Sets up both structlog and standard library logging with the provided
    configuration, including console and optional file output.

    Args:
        config: Complete logging configuration to apply
    """
    shared_processors = create_shared_processors()
    handlers = [create_console_handler(config.config.console, shared_processors)]

    if config.file_path is not None:
        file_config = _create_file_config(config)
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


def _create_file_config(config: LoggingConfig) -> FileHandlerConfig:
    """Create the file handler configuration.

    Determines the appropriate file path based on the configuration and
    builder settings.

    Args:
        config: Complete logging configuration

    Returns:
        File handler configuration with the resolved path and enabled state
    """
    file_config = config.config.file
    # Check if the custom file path is not empty
    if config.file_path:
        return replace(file_config, path=config.file_path, enabled=True)

    return file_config


def _configure_logging_system(level: str, handlers: list[logging.Handler]) -> None:
    """Configure the logging system with the specified handlers.

    Sets up both the root logger and any existing loggers with the provided configuration.
    This ensures consistent handling across all loggers.

    Args:
        level:      Logging level to set
        handlers:   List of handlers to add to loggers
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
