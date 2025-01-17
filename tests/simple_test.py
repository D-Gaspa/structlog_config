"""Example usage of the custom logging configuration."""

from pathlib import Path

import structlog

from structlog_config import configure_logging, get_logger


def demonstrate_logging_features(logger: structlog.stdlib.BoundLogger) -> None:
    """Demonstrate various logging features.

    Args:
        logger: Configured logger instance
    """
    # Structured logging with additional context
    logger = logger.bind(user_id="123", service="example_service")
    logger.info("Application started", version="1.0.0")

    # Exception logging
    try:
        result = 1 / 0
        print(result)  # This won't execute
    except ZeroDivisionError:
        logger.exception("Error dividing by zero")

    # Context variables (thread/async safe)
    with structlog.contextvars.bound_contextvars(request_id="abc-123"):
        logger.info("Processing request")
        logger.warning("Resource usage high", cpu_usage=85, memory_usage=90)


def main() -> None:
    """Main entry point demonstrating different configuration options."""
    # 1. Configure with the relative path from the config file
    print("\n=== Using Config File ===")
    config_path = Path(__file__).parent.parent / "config" / "logging.toml"
    configure_logging(config_path).with_file().build()

    logger = get_logger(__name__)
    logger.info("Logging with config file path")
    demonstrate_logging_features(logger)

    # 2. Try to reconfigure with a different path (should fail)
    print("=== Attempting to Reconfigure ===")
    try:
        # Using a relative path (which would work if not for the reconfiguration check)
        configure_logging().with_file("../other_logs/app.log").build()
        print("ERROR: Should not reach this line!")
    except RuntimeError as e:
        print(f"Expected error: {e}")
        logger.info("Reconfiguration properly prevented")

    # 3. Show that original logging still works
    print("\n=== Continuing with Original Configuration ===")
    logger = get_logger("different_logger")
    logger.info("Still using original configuration")


if __name__ == "__main__":
    main()
