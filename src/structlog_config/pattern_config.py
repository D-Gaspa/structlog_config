"""Pattern-based logging level configuration.

This module provides pattern-based logging level configuration support,
allowing fine-grained control over logger levels using glob-style patterns.
"""

import fnmatch
from dataclasses import dataclass

from .config import VALID_LOG_LEVELS, LogLevel


@dataclass(frozen=True, slots=True)
class PatternLevel:
    """A single pattern-level configuration pair.

    Represents a glob-style pattern and its associated logging level.
    Patterns are matched against logger names to determine the appropriate level.
    For example, a pattern of "app.*" would match loggers like "app.module".

    Attributes:
        pattern:    Glob-style pattern to match against logger names
        level:      Logging level to apply to matching loggers
    """

    pattern: str
    level: LogLevel

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If the pattern is empty or level is invalid
        """
        if not self.pattern:
            msg = "Pattern cannot be empty"
            raise ValueError(msg)

        if self.level not in VALID_LOG_LEVELS:
            msg = (
                f"Invalid logging level: {self.level!r}. "
                f"Must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}"
            )
            raise ValueError(msg)

    def matches(self, logger_name: str) -> bool:
        """Check if a logger name matches this pattern.

        Args:
            logger_name: Name of the logger to check

        Returns:
            True if the logger name matches the pattern, False otherwise
        """
        return fnmatch.fnmatch(logger_name, self.pattern)


@dataclass(frozen=True, slots=True)
class PatternLevelConfig:
    """Configuration for pattern-based logging levels.

    Maintains an ordered list of pattern-level pairs and provides
    functionality to find matching patterns for logger names.

    Attributes:
        patterns: List of pattern-level configurations in priority order
    """

    patterns: tuple[PatternLevel, ...] = ()

    def with_pattern(self, pattern: str, level: LogLevel) -> "PatternLevelConfig":
        """Create a new instance with an additional pattern-level pair.

        The new pattern is added at the end of the list, giving it
        lower priority than existing patterns.

        Args:
            pattern:    Glob-style pattern to match logger names
            level:      Logging level to apply to matching loggers

        Returns:
            New PatternLevelConfig instance with the additional pattern
        """
        new_pattern = PatternLevel(pattern, level)
        return PatternLevelConfig(patterns=(*self.patterns, new_pattern))

    def get_level_for_logger(self, logger_name: str) -> str | None:
        """Get the appropriate logging level for a logger name.

        Checks patterns in order (first match wins) to determine
        the logging level for the given logger name.

        Args:
            logger_name: Name of the logger to check

        Returns:
            Matching log level or None if no patterns match
        """
        for pattern in self.patterns:
            if pattern.matches(logger_name):
                return pattern.level
        return None
