"""Log level definitions and validation constants."""

from typing import Literal, get_args

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
VALID_LOG_LEVELS = frozenset(get_args(LogLevel))
