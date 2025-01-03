"""Logging configuration module."""

import logging
import logging.handlers
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import structlog


def get_project_root() -> Path:
    """Get the project root directory.

    This assumes the logging config is in src/utils/logging_config.py
    and will return the parent directory of 'src'.
    """
    return Path(__file__).parent.parent.parent


@dataclass
class LogConfig:
    """Logging configuration dataclass."""

    level: str
    format: str
    file_path: Path
    file_max_size: int
    file_backup_count: int
    file_encoding: str
    console_colors: bool
    console_rich_tracebacks: bool

    @classmethod
    def from_toml(cls, config_path: Path) -> "LogConfig":
        """Create LogConfig from the TOML file."""
        if not config_path.exists():
            msg = f"Configuration file not found: {config_path}"
            raise FileNotFoundError(msg)

        with config_path.open("rb") as f:
            config = tomllib.load(f)
            logging_config = config["logging"]

            root_dir = get_project_root()
            file_path = root_dir / logging_config["file"]["path"]

            return cls(
                level=logging_config["level"],
                format=logging_config["format"],
                file_path=file_path,
                file_max_size=logging_config["file"]["max_size"],
                file_backup_count=logging_config["file"]["backup_count"],
                file_encoding=logging_config["file"]["encoding"],
                console_colors=logging_config["console"]["colors"],
                console_rich_tracebacks=logging_config["console"]["rich_tracebacks"]
            )


def configure_logging(config_path: Path | None = None) -> None:
    """Configure structlog and standard library logging using TOML configuration."""
    root_dir = get_project_root()

    # If no config_path provided, use default relative to project root
    if config_path is None:
        config_path = root_dir / "config" / "logging.toml"

    try:
        config = LogConfig.from_toml(config_path)
    except FileNotFoundError as e:
        print(f"Error loading logging configuration: {e}. Using defaults.", file=sys.stderr)
        config = LogConfig(
            level="INFO",
            format="json",
            file_path=root_dir / "logs" / "app.log",
            file_max_size=10 * 1024 * 1024,
            file_backup_count=5,
            file_encoding="utf-8",
            console_colors=True,
            console_rich_tracebacks=True
        )

    # Ensure the logs directory exists
    config.file_path.parent.mkdir(parents=True, exist_ok=True)

    timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        timestamper,
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(
                colors=config.console_colors,
                exception_formatter=structlog.dev.rich_traceback if config.console_rich_tracebacks else None
            ),
        ],
    )

    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(indent=None),
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=config.file_path,
        maxBytes=config.file_max_size,
        backupCount=config.file_backup_count,
        encoding=config.file_encoding,
    )
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(config.level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
