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

from .config import FileHandlerConfig, LogConfig, LogLevel
from .handlers import create_console_handler, create_file_handler, create_shared_processors
from .pattern_config import PatternLevelConfig


@dataclass(frozen=True)
class RuntimeConfig:
    """Internal configuration state holder.

    This class maintains the complete logging configuration state including both
    the base configuration and file-specific settings.

    Attributes:
        base_config:    Base logging configuration from TOML or defaults
        file_path:      Optional custom path for file logging
    """

    base_config: LogConfig
    file_path: Path | None = None

    @property
    def file_config(self) -> FileHandlerConfig | None:
        """Get the effective file configuration.

        Returns:
            FileHandlerConfig if file logging is enabled, None otherwise
        """
        if not self.base_config.file and not self.file_path:
            return None

        if not self.file_path:
            return self.base_config.file

        if not self.base_config.file:
            return FileHandlerConfig(
                path=self.file_path,
                max_size=10 * 1024 * 1024,  # 10MB
                backup_count=5
            )

        return replace(self.base_config.file, path=self.file_path)


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
        self._state: RuntimeConfig | None = None
        self._lock: Final = threading.Lock()

    def is_configured(self) -> bool:
        """Check if logging has been fully configured.

        Returns:
            True if logging has been configured, False otherwise
        """
        return self._state is not None

    def get_config(self) -> RuntimeConfig:
        """Get the current configuration state.

        Returns:
            Current logging configuration

        Raises:
            RuntimeError: If logging hasn't been configured yet
        """
        if not self.is_configured():
            msg = (
                "Logging hasn't been configured. "
                "Call configure_logging() first or use default console-only logging."
            )
            raise RuntimeError(msg)
        return self._state

    def set_config(self, config: RuntimeConfig) -> None:
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


@dataclass
class LoggingBuilder:
    """Builder for logging configuration.

    Provides a fluent interface for configuring logging settings, including
    optional file logging with custom paths and pattern-based logging levels.
    The builder ensures a clean configuration process and maintains
    immutability of the underlying configuration objects.

    Attributes:
        _base_config:   Base logging configuration from TOML or defaults
        _file_path:     Optional custom path for file logging output
    """

    _base_config: LogConfig
    _file_path: Path | None = None

    def with_file(self, path: str | Path | None = None) -> "LoggingBuilder":
        """Add file logging with an optional custom path.

        If a path is provided, it can be either relative or absolute.
        Relative paths are resolved from the current working directory.
        If no path is provided but file configuration exists in the base
        config, that configuration will be used.

        Args:
            path: Optional custom log file path.
                    If provided, it overrides any path from the configuration file.

        Returns:
            Self for method chaining
        """
        if path is not None:
            self._file_path = Path(path)

        return self

    def with_pattern_level(self, pattern: str, level: LogLevel) -> "LoggingBuilder":
        """Add a pattern-based logging level configuration.

        Patterns are glob-style (e.g., "sqlalchemy.*") and are matched against
        logger names to determine the appropriate logging level.
        Patterns are checked in the order they are added, with later patterns
        taking precedence.

        Args:
            pattern:    Glob-style pattern to match logger names
            level:      Logging level to apply to matching loggers

        Returns:
            Self for method chaining
        """
        patterns = self._base_config.pattern_levels.with_pattern(pattern, level)
        self._base_config = replace(self._base_config, pattern_levels=patterns)
        return self

    def build(self) -> None:
        """Build and apply the logging configuration.

        This method finalizes the configuration and sets up the logging system.
        It can only be called once per application lifecycle due to the global
        nature of the logging configuration.

        The build process:
        1. Creates a runtime configuration combining base config and custom settings
        2. Validates and applies the configuration globally
        3. Sets up both structlog and standard library logging systems
        """
        config = RuntimeConfig(
            base_config=self._base_config,
            file_path=self._file_path,
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
    config = (
        LogConfig.from_toml(Path(config_path))
        if config_path is not None
        else LogConfig.create_default()
    )

    return LoggingBuilder(config)


def get_logger(name: str | None = None) -> BoundLogger:
    """Get a configured structlog logger instance.

    Creates or retrieves a structured logger with the specified name.
    If logging hasn't been configured yet, returns a console-only logger.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    if not _config_state.is_configured():
        _configure_console_only()
    return structlog.get_logger(name)


def _configure_console_only() -> None:
    """Configure basic console-only logging.

    Sets up a minimal logging configuration that only outputs to the console.
    This is used as a fallback when logging is accessed before configuration.
    """
    config = LogConfig.create_default()
    shared_processors = create_shared_processors()
    console_handler = create_console_handler(config.console, shared_processors)

    _configure_logging_system(
        level=config.level,
        handlers=[console_handler]
    )


def _configure_logging(config: RuntimeConfig) -> None:
    """Configure the logging system with the specified configuration.

    Sets up both structlog and standard library logging with the provided
    configuration, including console and optional file output.

    Args:
        config: Complete logging configuration to apply
    """
    shared_processors = create_shared_processors()
    handlers = [create_console_handler(config.base_config.console, shared_processors)]

    if file_config := config.file_config:
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
        level=config.base_config.level,
        handlers=handlers,
        pattern_levels=config.base_config.pattern_levels
    )


def _configure_logging_system(
        level: str,
        handlers: list[logging.Handler],
        pattern_levels: PatternLevelConfig | None = None
) -> None:
    """Configure the logging system with the specified handlers and patterns.

    Sets up both the root logger and any existing loggers with the provided
    configuration.
    This ensures consistent handling across all loggers while respecting
    pattern-based level configurations.

    Args:
        level:          Default logging level to set
        handlers:       List of handlers to add to loggers
        pattern_levels: Optional pattern-based logging level configuration
    """
    _configure_root_logger(level, handlers)
    _configure_existing_loggers(level, handlers, pattern_levels)


def _configure_root_logger(level: str, handlers: list[logging.Handler]) -> None:
    """Configure the root logger with the specified settings.

    The root logger is the base logger that all other loggers inherit from by default.
    This function ensures it has the correct level and handlers set.

    Args:
        level:      Logging level to set for the root logger
        handlers:   List of handlers to attach to the root logger
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # We only want our handlers

    for handler in handlers:
        root_logger.addHandler(handler)

    root_logger.setLevel(level)


def _configure_existing_loggers(
        level: str,
        handlers: list[logging.Handler],
        pattern_levels: PatternLevelConfig | None = None
) -> None:
    """Configure all existing loggers in the logging system.

    This function updates all non-root loggers that have been created,
    ensuring they have the correct handlers and levels set according to
    both the default configuration and any pattern-based rules.

    Args:
        level:          Default logging level to set
        handlers:       List of handlers to add to each logger
        pattern_levels: Optional pattern-based logging level configuration
    """
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if not isinstance(logger, logging.Logger) or logger_name == "root":
            continue

        _configure_logger(logger, level, handlers, pattern_levels)


def _configure_logger(
        logger: logging.Logger,
        level: str,
        handlers: list[logging.Handler],
        pattern_levels: PatternLevelConfig | None = None
) -> None:
    """Configure a single logger with the specified settings.

    Sets up an individual logger with the appropriate handlers and level.
    The level can be determined either by the default level or by matching
    patterns if pattern-based configuration is provided.

    Args:
        logger:         Logger instance to configure
        level:          Default logging level to set
        handlers:       List of handlers to add to the logger
        pattern_levels: Optional pattern-based logging level configuration
    """
    logger.handlers.clear()
    for handler in handlers:
        logger.addHandler(handler)
    logger.propagate = False

    # Apply pattern-based level if available and matching
    if (
            pattern_levels is not None
            and (pattern_level := pattern_levels.get_level_for_logger(logger.name))
    ):
        logger.setLevel(pattern_level)
        return

    # Use default level if no patterns match or patterns not configured
    logger.setLevel(level)
