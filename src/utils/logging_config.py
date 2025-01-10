"""Structured logging configuration with file and console output support.

This module provides a flexible logging configuration system that supports both file and console outputs with
structured logging via structlog and standard library logging.

Examples:
    configure_logging()  # Use default configuration
    logger = get_logger(__name__)
    logger.info("Application started", version="1.0.0")

Configuration:
    The logging configuration can be specified in a TOML file with the following structure:
    [logging]
    level = "INFO"

    [logging.file]
    path = "logs/app.log"
    max_size = 10485760 # 10MB
    backup_count = 5
    encoding = "utf-8"

    [logging.console]
    colors = true
    rich_tracebacks = true
"""

import logging
import logging.handlers
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, get_args

import structlog
from structlog.types import Processor

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(get_args(LogLevel))


@dataclass(frozen=True, slots=True)
class FileHandlerConfig:
    """Configuration for file-based logging output.

    Attributes:
        path:           Path to the log file.
        max_size:       Maximum size of the log file in bytes before rotating.
        backup_count:   Number of backup log files to keep before overwriting.
        encoding:       Encoding for the log file (default: "utf-8").
    """

    path: Path
    max_size: int
    backup_count: int
    encoding: str = "utf-8"


@dataclass(frozen=True, slots=True)
class ConsoleHandlerConfig:
    """Configuration for console-based logging output.

    Attributes:
        colors:             Enable colored output for the console (requires 'colorama' library).
        rich_tracebacks:    Enable rich tracebacks for exceptions (requires 'rich' library).
    """

    colors: bool
    rich_tracebacks: bool


@dataclass(frozen=True, slots=True)
class LogConfig:
    """Complete logging configuration settings.

    Coordinates both file and console logging settings while enforcing validation rules.
    Supports creation from TOML configuration files and provides sensible defaults when needed.

    Attributes:
        level:      Logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        file:       FileHandlerConfig instance for file-based logging settings.
        console:    ConsoleHandlerConfig instance for console-based logging settings.
    """

    level: LogLevel
    file: FileHandlerConfig
    console: ConsoleHandlerConfig

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If the logging level is invalid or if file settings are invalid
        """
        if self.level not in VALID_LOG_LEVELS:
            msg = (
                f"Invalid logging level: {self.level!r}. "
                f"Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
            )
            raise ValueError(msg)

        if self.file.max_size <= 0:
            msg = "max_size must be a positive integer (bytes)"
            raise ValueError(msg)

        if self.file.backup_count < 0:
            msg = "backup_count must be a non-negative integer"
            raise ValueError(msg)

    @classmethod
    def from_toml(cls, config_path: Path) -> "LogConfig":
        """Create LogConfig instance from a TOML configuration file.

        Args:
            config_path: Path to the TOML configuration file

        Returns:
            LogConfig instance with the parsed configuration

        Raises:
            FileNotFoundError:  If the configuration file doesn't exist
            TOMLDecodeError:    If the TOML file is malformed
            ValueError:         If required configuration keys are missing or if values are invalid
        """
        try:
            with config_path.open("rb") as f:
                config_data = tomllib.load(f)

        except FileNotFoundError as e:
            msg = f"Configuration file not found: {config_path}"
            raise FileNotFoundError(msg) from e

        except tomllib.TOMLDecodeError as e:
            msg = f"Failed to parse TOML file {config_path}"
            raise tomllib.TOMLDecodeError(msg) from e

        try:
            logging_config = config_data["logging"]

            file_config = FileHandlerConfig(
                path=Path(logging_config["file"]["path"]),
                max_size=int(logging_config["file"]["max_size"]),
                backup_count=int(logging_config["file"]["backup_count"]),
                encoding=logging_config["file"].get("encoding", "utf-8"),
            )

            console_config = ConsoleHandlerConfig(
                colors=bool(logging_config["console"]["colors"]),
                rich_tracebacks=bool(logging_config["console"]["rich_tracebacks"])
            )

            return cls(
                level=logging_config["level"].upper(),
                file=file_config,
                console=console_config
            )

        except KeyError as e:
            msg = f"Missing required configuration key in configuration file: {e.args[0]}"
            raise ValueError(msg) from e

        except (TypeError, ValueError) as e:
            msg = f"Invalid value in configuration file: {e!s}"
            raise ValueError(msg) from e

    @classmethod
    def create_default(cls, root_dir: Path) -> "LogConfig":
        """Create a default LogConfig instance.

        The default configuration uses INFO level logging with a rotating file handler of 10MB and 5 backups.
        There is also a console handler with colored output and rich tracebacks.

        Args:
            root_dir: Project root directory for relative path resolution

        Returns:
            LogConfig instance with default settings
        """
        return cls(
            level="INFO",
            file=FileHandlerConfig(
                path=root_dir / "logs" / "app.log",
                max_size=10 * 1024 * 1024,  # 10MB
                backup_count=5
            ),
            console=ConsoleHandlerConfig(
                colors=True,
                rich_tracebacks=True
            )
        )


class LoggerFactory:
    """Factory class for creating and configuring loggers.

    This class is responsible for creating and configuring the console and file log handlers
    with the shared structlog processors.

    Attributes:
        config:             LogConfig instance containing logger settings
        _shared_processors: List of shared structlog processors for both console and file output
    """

    def __init__(self, config: LogConfig) -> None:
        """Initialize the logger factory with configuration.

        Args:
            config: LogConfig instance containing logger settings
        """
        self.config = config
        self._shared_processors = self.create_shared_processors()

    @staticmethod
    def create_shared_processors() -> list[Processor]:
        """Create the list of shared structlog processors.

        Returns:
            List of structlog processors for both console and file output
        """
        return [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.ExtraAdder(),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        ]

    def create_console_handler(self) -> logging.Handler:
        """Create and configure the console log handler.

        Returns:
            Configured StreamHandler instance
        """
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=self._shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(
                    colors=self.config.console.colors,
                    exception_formatter=(
                        structlog.dev.rich_traceback
                        if self.config.console.rich_tracebacks
                        else None
                    )
                ),
            ],
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        return handler

    def create_file_handler(self) -> logging.Handler:
        """Create and configure the file log handler.

        Returns:
            Configured RotatingFileHandler instance
        """
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=self._shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(indent=None),
            ],
        )

        handler = logging.handlers.RotatingFileHandler(
            filename=self.config.file.path,
            maxBytes=self.config.file.max_size,
            backupCount=self.config.file.backup_count,
            encoding=self.config.file.encoding,
        )
        handler.setFormatter(formatter)
        return handler


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path to the project root (parent directory of 'src')
    """
    return Path(__file__).parent.parent.parent


def configure_logging(config_path: Path | None = None) -> None:
    """Configure structlog and standard library logging.

    Args:
        config_path: Optional path to a TOML config file.
                     If None, it will use the default logging.toml file.
    """
    root_dir = get_project_root()

    if config_path is None:
        config_path = root_dir / "config" / "logging.toml"

    try:
        config = LogConfig.from_toml(config_path)

    except FileNotFoundError as e:
        print(f"Error loading logging configuration: {e}. Using defaults.", file=sys.stderr)
        config = LogConfig.create_default(root_dir)

    config.file.path.parent.mkdir(parents=True, exist_ok=True)

    # Configure structlog
    factory = LoggerFactory(config)

    structlog.configure(
        processors=[
            *factory.create_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create and configure handlers
    console_handler = factory.create_console_handler()
    file_handler = factory.create_file_handler()

    # Configure loggers
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(config.level)

    _configure_existing_loggers(
        level=config.level,
        handlers=[console_handler, file_handler]
    )

    # Log successful configuration
    logger = get_logger(__name__)
    logger.info("Logging configured", config_path=str(config_path))


def _configure_existing_loggers(level: str, handlers: list[logging.Handler]) -> None:
    """Configure all existing loggers to use the specified handlers.

    Args:
        level:      Logging level to set
        handlers:   List of handlers to add to each logger
    """
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if not isinstance(logger, logging.Logger) or logger_name == "root":
            continue
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger instance.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    return structlog.get_logger(name)
