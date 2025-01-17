# structlog-config

A flexible configuration system for structured logging in Python using `structlog` and the standard library logging.
This package provides a clean, type-safe interface for setting up logging with both file and console outputs.

## Features

- 🔄 Rotating file output with configurable size and backup count
- 🎨 Colored console output with rich tracebacks
- ⚙️ TOML-based configuration with sensible defaults
- 🔍 Structured logging with JSON formatting for file output
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

Basic usage with default configuration:

```python
from structlog_config import configure_logging, get_logger

# Setup logging (creates logs/ directory if needed)
configure_logging()

# Get a logger and start logging!
logger = get_logger(__name__)
logger.info("Application started", version="1.0.0")
```

## Configuration

Logging can be configured using a TOML file. Create a file named `logging.toml`:

```toml
[logging]
level = "INFO"

[logging.file]
path = "logs/app.log"
max_size = 10485760  # 10MB
backup_count = 5
encoding = "utf-8"

[logging.console]
colors = true
rich_tracebacks = true
```

Then use it in your code:

```python
from pathlib import Path
from structlog_config import configure_logging

configure_logging(Path("logging.toml"))
```

### Default Configuration

If no configuration file is provided, the following defaults are used:

- Logging level: INFO
- Log file: `./logs/app.log`
- Maximum file size: 10MB
- Backup count: 5
- Console output: Colored with rich tracebacks

### Structured Logging

Add context to your logs with structured data:

```python
from structlog_config import get_logger

logger = get_logger(__name__)

# Add structured data
logger.info(
    "User logged in",
    user_id="12345",
    ip_address="192.168.1.1",
    login_method="oauth2"
)

# Log exceptions with context
try:
    raise ValueError("Invalid input")
except ValueError:
    logger.exception(
        "Login failed",
        user_id="12345",
        attempt=3
    )
```

## Requirements

- Python 3.10+
- structlog>=24.4.0
- rich>=13.9.4
- colorama>=0.4.6

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.