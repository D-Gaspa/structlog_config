"""Configuration handling for structured logging.

This module provides configuration classes and TOML parsing functionality for the
structured logging system. It defines the configuration schema and validation rules
for both file and console logging outputs.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, get_args

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(get_args(LogLevel))


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
    """

    path: Path
    max_size: int
    backup_count: int
    encoding: str = "utf-8"

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

    This class coordinates both file and console logging settings while enforcing validation rules.
    It supports creation from TOML configuration files and provides sensible defaults when needed.

    Attributes:
        level:      Logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file:       FileHandlerConfig instance for file-based logging settings
        console:    ConsoleHandlerConfig instance for console-based logging settings
    """

    level: LogLevel
    file: FileHandlerConfig
    console: ConsoleHandlerConfig

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If the logging level is invalid
        """
        if self.level not in VALID_LOG_LEVELS:
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
            file=cls._create_file_config(logging_config["file"]),
            console=cls._create_console_config(logging_config["console"])
        )

    @staticmethod
    def _create_file_config(file_config: dict) -> FileHandlerConfig:
        """Create a FileHandlerConfig from the configuration dictionary.

        Args:
            file_config: Dictionary containing file handler configuration

        Returns:
            Configured FileHandlerConfig instance
        """
        return FileHandlerConfig(
            path=Path(file_config["path"]),
            max_size=int(file_config["max_size"]),
            backup_count=int(file_config["backup_count"]),
            encoding=file_config.get("encoding", "utf-8")
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
            colors=bool(console_config["colors"]),
            rich_tracebacks=bool(console_config["rich_tracebacks"])
        )

    @classmethod
    def create_default(cls, log_dir: Path) -> "LogConfig":
        """Create a default LogConfig instance.

        Creates a configuration with sensible defaults:
        - INFO level logging
        - 10MB rotating file with 5 backups
        - Colored console output with rich tracebacks

        Args:
            log_dir: Directory where log files will be stored

        Returns:
            LogConfig instance with default settings
        """
        return cls(
            level="INFO",
            file=FileHandlerConfig(
                path=log_dir / "app.log",
                max_size=10 * 1024 * 1024,  # 10MB
                backup_count=5
            ),
            console=ConsoleHandlerConfig(
                colors=True,
                rich_tracebacks=True
            )
        )
