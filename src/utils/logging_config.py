"""
Structured logging configuration with file and console output support.

This module provides a flexible logging configuration system that supports both file and console outputs with
structured logging via structlog and standard library logging.
"""

import logging
import logging.handlers
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import structlog
from structlog.types import Processor


@dataclass(frozen=True)
class FileHandlerConfig:
    """Configuration for file-based logging output."""

    path: Path
    max_size: int
    backup_count: int
    encoding: str = "utf-8"


@dataclass(frozen=True)
class ConsoleHandlerConfig:
    """Configuration for console-based logging output."""

    colors: bool
    rich_tracebacks: bool


@dataclass(frozen=True)
class LogConfig:
    """Complete logging configuration settings."""

    level: str
    format: str
    file: FileHandlerConfig
    console: ConsoleHandlerConfig

    @classmethod
    def from_toml(cls, config_path: Path) -> "LogConfig":
        """Create LogConfig instance from a TOML configuration file.

        Args:
            config_path: Path to the TOML configuration file

        Returns:
            LogConfig instance with the parsed configuration

        Raises:
            FileNotFoundError: If the configuration file doesn't exist
        """
        if not config_path.exists():
            msg = f"Configuration file not found: {config_path}"
            raise FileNotFoundError(msg)

        with config_path.open("rb") as f:
            config = tomllib.load(f)
            logging_config = config["logging"]

            file_config = FileHandlerConfig(
                path=Path(logging_config["file"]["path"]),
                max_size=logging_config["file"]["max_size"],
                backup_count=logging_config["file"]["backup_count"],
                encoding=logging_config["file"]["encoding"],
            )

            console_config = ConsoleHandlerConfig(
                colors=logging_config["console"]["colors"],
                rich_tracebacks=logging_config["console"]["rich_tracebacks"]
            )

            return cls(
                level=logging_config["level"],
                format=logging_config["format"],
                file=file_config,
                console=console_config
            )

    @classmethod
    def create_default(cls, root_dir: Path) -> "LogConfig":
        """Create a default LogConfig instance.

        Args:
            root_dir: Project root directory for relative path resolution

        Returns:
            LogConfig instance with default settings
        """
        return cls(
            level="INFO",
            format="json",
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
    """Factory class for creating and configuring loggers."""

    def __init__(self, config: LogConfig):
        """Initialize the logger factory with configuration.

        Args:
            config: LogConfig instance containing logger settings
        """
        self.config = config
        self._shared_processors = self.create_shared_processors()

    @staticmethod
    def create_shared_processors() -> List[Processor]:
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


def configure_logging(config_path: Optional[Path] = None) -> None:
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
        print(f"Error loading logging configuration: {e}. Using defaults.",
              file=sys.stderr)
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


def _configure_existing_loggers(level: str, handlers: List[logging.Handler]) -> None:
    """Configure all existing loggers to use the specified handlers.

    Args:
        level: Logging level to set
        handlers: List of handlers to add to each logger
    """
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if not isinstance(logger, logging.Logger) or logger_name == "root":
            continue
        logger.handlers.clear()
        for handler in handlers:
            logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(level)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger instance.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    return structlog.get_logger(name)
