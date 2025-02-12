"""Configuration handling for structured logging.

This module provides configuration classes and TOML parsing functionality for the
structured logging system. It defines the configuration schema and validation rules
for both file and console logging outputs.
"""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import tomllib

from .log_levels import VALID_LOG_LEVELS, LogLevel
from .pattern_config import PatternLevelConfig


@dataclass(frozen=True, slots=True)
class FileHandlerConfig:
    """Configuration for file-based logging output.

    This class defines the settings for rotating file handler configuration,
    including file location, size limits, and rotation behavior.

    Attributes:
        path:           Path to the log file
        max_size:       Maximum size of the log file in bytes before rotating
        backup_count:   Number of backup log files to keep before overwriting
        encoding:       Character encoding for the log file (default: utf-8)
        enabled:        Enable file-based logging (default: False)
    """

    path: Path
    max_size: int
    backup_count: int
    encoding: str = "utf-8"
    enabled: bool = field(default=False)

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If max_size is not positive or backup_count is negative
        """
        if self.max_size <= 0:
            msg = "max_size must be a positive integer (bytes)"
            raise ValueError(msg)

        if self.backup_count < 0:
            msg = "backup_count must be a non-negative integer"
            raise ValueError(msg)

    def with_path(self, new_path: Path) -> "FileHandlerConfig":
        """Create a new instance with an updated path.

        Args:
            new_path: New log file path

        Returns:
            New FileHandlerConfig instance with the updated path
        """
        self._validate_path(new_path)
        return replace(self, path=new_path, enabled=True)

    def enable(self) -> "FileHandlerConfig":
        """Create a new instance with file logging enabled.

        Returns:
            New FileHandlerConfig instance with file logging enabled
        """
        return replace(self, enabled=True)

    @staticmethod
    def _validate_path(path: Path) -> None:
        """Validate the log file path.

        Args:
            path: Path to validate

        Raises:
            ValueError: If the path is invalid
        """
        try:
            # Resolve the path to handle relative paths (../../etc) correctly
            resolved_path = Path.cwd() / path if not path.is_absolute() else path
            parent = resolved_path.parent

            if not parent.exists() or os.access(parent, os.W_OK):
                return
            msg = f"Log directory is not writable: {parent}"
            raise ValueError(msg)

        except OSError as e:
            msg = f"Invalid log file path: {path}. Error: {e}"
            raise ValueError(msg) from e


@dataclass(frozen=True, slots=True)
class ConsoleHandlerConfig:
    """Configuration for console-based logging output.

    This class defines settings for console output formatting, including
    color support and traceback rendering options.

    Attributes:
        colors:             Enable colored output for the console (requires 'colorama' library)
        rich_tracebacks:    Enable rich tracebacks formatting (requires 'rich' library)
    """

    colors: bool
    rich_tracebacks: bool


@dataclass(frozen=True, slots=True)
class LogConfig:
    """Complete logging configuration settings.

    This class coordinates logging settings while enforcing validation rules.
    It supports the creation of a TOML configuration file and provides sensible defaults.

    Attributes:
        level:          Logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file:           FileHandlerConfig instance for file-based logging settings
        console:        ConsoleHandlerConfig instance for console-based logging settings
        pattern_levels: PatternLevelConfig for fine-grained logger level control
    """

    level: LogLevel
    file: FileHandlerConfig
    console: ConsoleHandlerConfig
    pattern_levels: PatternLevelConfig

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If the logging level is invalid
        """
        if self.level in VALID_LOG_LEVELS:
            return
        msg = (
            f"Invalid logging level: {self.level!r}. "
            f"Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
        )
        raise ValueError(msg)

    @classmethod
    def from_toml(cls, config_path: Path) -> "LogConfig":
        """Create LogConfig instance from a TOML configuration file.

        Args:
            config_path: Path to the TOML configuration file

        Returns:
            Configured LogConfig instance

        Raises:
            ValueError: If required configuration keys are missing or if values are invalid
        """
        try:
            config_data = cls._load_toml(config_path)
            return cls._parse_config(config_data)

        except KeyError as e:
            msg = f"Missing required configuration key: {e.args[0]}"
            raise ValueError(msg) from e

        except (TypeError, ValueError) as e:
            msg = f"Invalid value in configuration file: {e!s}"
            raise ValueError(msg) from e

    @classmethod
    def _load_toml(cls, config_path: Path) -> dict:
        """Load and parse the TOML configuration file.

        Args:
            config_path: Path to the TOML configuration file

        Returns:
            Parsed configuration dictionary

        Raises:
            FileNotFoundError:  If the configuration file doesn't exist
            TOMLDecodeError:    If the TOML file is malformed
        """
        try:
            with config_path.open("rb") as f:
                return tomllib.load(f)

        except FileNotFoundError as e:
            msg = f"Configuration file not found: {config_path}"
            raise FileNotFoundError(msg) from e

        except tomllib.TOMLDecodeError as e:
            msg = f"Failed to parse TOML file {config_path}"
            raise tomllib.TOMLDecodeError(msg) from e

    @classmethod
    def _parse_config(cls, config_data: dict) -> "LogConfig":
        """Parse the configuration dictionary into a LogConfig instance.

        Args:
            config_data: Dictionary containing the configuration data

        Returns:
            Configured LogConfig instance
        """
        logging_config = config_data["logging"]

        return cls(
            level=logging_config["level"].upper(),
            file=cls._create_file_config(logging_config.get("file", {})),
            console=cls._create_console_config(logging_config.get("console", {})),
            pattern_levels=cls._create_pattern_config(logging_config.get("patterns", {}))
        )

    @staticmethod
    def _create_file_config(file_config: dict) -> FileHandlerConfig:
        """Create a FileHandlerConfig from the configuration dictionary.

        Args:
            file_config: Dictionary containing file handler configuration

        Returns:
            Configured FileHandlerConfig instance
        """
        if not file_config:
            # Return disabled file logging if no config provided
            return FileHandlerConfig(
                path=Path("logs/app.log"),
                max_size=10 * 1024 * 1024,  # 10MB
                backup_count=5,
                enabled=False
            )

        return FileHandlerConfig(
            path=Path(file_config["path"]),
            max_size=int(file_config["max_size"]),
            backup_count=int(file_config["backup_count"]),
            encoding=file_config.get("encoding", "utf-8"),
            enabled=True
        )

    @staticmethod
    def _create_console_config(console_config: dict) -> ConsoleHandlerConfig:
        """Create a ConsoleHandlerConfig from the configuration dictionary.

        Args:
            console_config: Dictionary containing console handler configuration

        Returns:
            Configured ConsoleHandlerConfig instance
        """
        return ConsoleHandlerConfig(
            colors=bool(console_config.get("colors", True)),
            rich_tracebacks=bool(console_config.get("rich_tracebacks", True))
        )

    @staticmethod
    def _create_pattern_config(pattern_config: dict) -> PatternLevelConfig:
        """Create a PatternLevelConfig from the configuration dictionary.

        Args:
            pattern_config: Dictionary containing pattern-level mappings

        Returns:
            Configured PatternLevelConfig instance
        """
        if not pattern_config:
            return PatternLevelConfig()

        config = PatternLevelConfig()
        # Process patterns in order they appear in the TOML
        for pattern, level in pattern_config.items():
            config = config.with_pattern(pattern, level.upper())

        return config

    @classmethod
    def create_default(cls, log_dir: Path) -> "LogConfig":
        """Create a default LogConfig instance.

        Creates a configuration with sensible defaults:
        - INFO level logging
        - Console logging enabled with colors and rich tracebacks
        - File logging disabled by default

        Args:
            log_dir: Directory where log files will be stored if enabled

        Returns:
            LogConfig instance with default settings
        """
        return cls(
            level="INFO",
            file=FileHandlerConfig(
                path=log_dir / "app.log",
                max_size=10 * 1024 * 1024,  # 10MB
                backup_count=5,
                enabled=False
            ),
            console=ConsoleHandlerConfig(
                colors=True,
                rich_tracebacks=True
            ),
            pattern_levels=PatternLevelConfig()
        )
