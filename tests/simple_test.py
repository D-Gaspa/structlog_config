"""Example usage of the custom logging configuration."""

from pathlib import Path

import structlog

from structlog_config import configure_logging, get_logger


def main() -> None:
    """Main entry point of the application."""
    config_path = Path(__file__).parent.parent / "config" / "logging.toml"
    configure_logging(config_path)

    logger = get_logger(__name__)
    logger = logger.bind(user_id="123", service="example_service")
    logger.info("Application started", version="1.0.0")

    try:
        result = 1 / 0
        print(result)
    except ZeroDivisionError:
        logger.exception("Error dividing by zero")

    # Using context variables (thread/async safe)
    with structlog.contextvars.bound_contextvars(request_id="abc-123"):
        logger.info("Processing request")
        logger.warning("Resource usage high", cpu_usage=85, memory_usage=90)


if __name__ == "__main__":
    main()
