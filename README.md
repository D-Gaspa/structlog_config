# structlog-config

A flexible configuration system for structured logging in Python using `structlog` and the standard library logging.
This package provides a clean, type-safe interface for setting up logging with both file and console outputs.

## Features

- 🎨 Colored console output with rich tracebacks (enabled by default)
- 🔄 Optional rotating file output with configurable size and backup count
- ⚙️ TOML-based configuration with sensible defaults
- 🔍 Structured logging with JSON formatting for file output
- 🛡️ Thread-safe configuration with single-configuration enforcement
- 📝 Console-only fallback for early logging access
- 💫 Exception information with full tracebacks
- 🕒 Local time timestamp formatting

## Installation

Install directly using `uv`:

```bash
uv add git+https://github.com/d-gaspa/structlog_config
```

or with `pip`:

```bash
pip install git+https://github.com/d-gaspa/structlog_config
```

## Quick Start

Basic usage with default configuration (console-only):

```python
from structlog_config import get_logger

# Start logging immediately with console-only output
logger = get_logger(__name__)
logger.info("Application started", version="1.0.0")
```

Enable file logging with a configuration file:

```python
from pathlib import Path
from structlog_config import configure_logging, get_logger

# Use configuration from a TOML file
config_path = Path("config/logging.toml")
configure_logging(config_path).with_file().build()

logger = get_logger(__name__)
logger.info("Logging configured with file output")
```

Custom file path (directory is created if needed):

```python
from structlog_config import configure_logging, get_logger

# Specify a custom log file path
configure_logging().with_file("logs/custom.log").build()

logger = get_logger(__name__)
logger.info("Logging to custom file path")
```

## Configuration

Logging can be configured using a TOML file. Create a file named `logging.toml`:

```toml
# All sections and fields are optional with sensible defaults
[logging]
level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

[logging.file]
path = "logs/app.log"
max_size = 10485760  # 10MB
backup_count = 5
encoding = "utf-8"

[logging.console]
colors = true
rich_tracebacks = true
```

### Default Configuration

The following defaults are used when no configuration is provided:

- Logging level: INFO
- Console output: Colored with rich tracebacks
- File logging: Disabled by default
    - When enabled:
        - Path: `./logs/app.log`
        - Maximum size: 10MB
        - Backup count: 5
        - UTF-8 encoding

## Structured Logging

Add context to your logs with structured data:

```python
from structlog_config import get_logger

# Get a logger
logger = get_logger(__name__)

# Add persistent context
logger = logger.bind(
    user_id="123",
    service="example_service"
)

# Log with additional context
logger.info(
    "User action completed",
    action="purchase",
    item_id="456",
    amount=29.99
)
```

### File Output Format (JSON)

When file logging is enabled, logs are written in JSON format for easy parsing:

```json
{
  "timestamp": "2025-01-17 10:30:45",
  "level": "info",
  "event": "User action completed",
  "logger": "example_app",
  "user_id": "123",
  "service": "example_service",
  "action": "purchase",
  "item_id": "456",
  "amount": 29.99
}
```

## Requirements

- Python 3.10+
- structlog>=24.4.0
- rich>=13.9.4
- colorama>=0.4.6

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.