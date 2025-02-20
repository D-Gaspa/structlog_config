"""Handler creation and configuration for structured logging.

This module provides factory functions for creating and configuring logging handlers
with structured logging support. It handles both file and console outputs with their
respective formatting and configuration options.
"""

import json
import logging
import logging.handlers
import os
import sys
from typing import Any

import structlog
from structlog.types import Processor

from .config import ConsoleHandlerConfig, FileHandlerConfig


def create_shared_processors() -> list[Processor]:
    """Create the list of shared structlog processors.

    These processors are used by both console and file handlers to provide
    consistent base formatting and enrichment of log records.

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


def create_console_handler(
        config: ConsoleHandlerConfig,
        shared_processors: list[Processor]
) -> logging.Handler:
    """Create and configure a console logging handler.

    Creates a StreamHandler with structlog formatting that outputs to stdout.
    Supports colored output and rich tracebacks if enabled in the configuration.

    Args:
        config:             Console handler configuration settings
        shared_processors:  List of shared structlog processors to use

    Returns:
        Configured StreamHandler instance
    """
    formatter = _create_console_formatter(config, shared_processors)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    return handler


def create_file_handler(
        config: FileHandlerConfig,
        shared_processors: list[Processor]
) -> logging.Handler:
    """Create and configure a file logging handler.

    Creates a RotatingFileHandler with structlog JSON formatting. Handles log
    rotation based on file size with backup file support.

    Args:
        config:             File handler configuration settings
        shared_processors:  List of shared structlog processors

    Returns:
        Configured RotatingFileHandler instance

    Raises:
        OSError:    If there are permission or path issues
        ValueError: If the configuration is invalid
    """
    if not config.enabled:
        msg = "Attempted to create file handler with disabled configuration"
        raise ValueError(msg)

    path = config.path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and not os.access(path, os.W_OK):
            msg = f"Log file is not writable: {path}"
            raise ValueError(msg)

        if path.parent.exists() and not os.access(path.parent, os.W_OK):
            msg = f"Log directory is not writable: {path.parent}"
            raise ValueError(msg)

        # Add newline to separate executions
        if path.exists() and path.stat().st_size > 0:
            with open(path, 'a', encoding=config.encoding) as f:
                f.write('\n')

    except OSError as e:
        msg = f"Failed to setup log file at {path}: {e}"
        raise OSError(msg) from e

    formatter = _create_file_formatter(shared_processors)
    handler = logging.handlers.RotatingFileHandler(
        filename=path,
        maxBytes=config.max_size,
        backupCount=config.backup_count,
        encoding=config.encoding,
    )
    handler.setFormatter(formatter)
    return handler


def _create_console_formatter(
        config: ConsoleHandlerConfig,
        shared_processors: list[Processor]
) -> structlog.stdlib.ProcessorFormatter:
    """Create a formatter for console output.

    Args:
        config:             Console handler configuration
        shared_processors:  List of shared structlog processors

    Returns:
        Configured ProcessorFormatter for console output
    """
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(
                colors=config.colors,
                exception_formatter=(
                    structlog.dev.rich_traceback
                    if config.rich_tracebacks
                    else None
                )
            ),
        ],
    )


def _create_file_formatter(
        shared_processors: list[Processor]
) -> structlog.stdlib.ProcessorFormatter:
    """Create a formatter for file output.

    Args:
        shared_processors: List of shared structlog processors

    Returns:
        Configured ProcessorFormatter for file output
    """
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(serializer=ordered_json_dumps),
        ],
    )


def ordered_json_dumps(dic: dict, **kwargs: dict[str, Any]) -> str:
    """Create an ordered JSON dump with event first and timestamp last.

    Args:
        dic:        Dictionary to serialize
        **kwargs:   Additional arguments passed to json.dumps

    Returns:
        JSON string with enforced field ordering
    """
    ordered = {}

    # Ensure event is first if present
    if "event" in dic:
        ordered["event"] = dic["event"]

    ordered.update({
        key: value for key, value in dic.items()
        if key not in {"event", "timestamp"}
    })

    # Add timestamp last if present
    if "timestamp" in dic:
        ordered["timestamp"] = dic["timestamp"]

    return json.dumps(ordered, **kwargs)
