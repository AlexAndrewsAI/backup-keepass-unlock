# backup-after-decrypting

A Python package for managing backup profiles with configuration management.

## Overview

This package provides:
- Modern Python packaging with `pyproject.toml`
- Type hints and static type checking with **mypy**
- Code linting with **ruff**
- Testing with **pytest**
- Dependency management with **uv**
- Backup profile management with YAML configuration

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/AlexAndrewsAI/python-package-template.git
cd backup-after-decrypting
uv sync
```

## Usage

### Command Line Interface

The package includes a CLI tool built with **typer**:

```bash
# List all backup profiles
uv run python -m backup_after_decrypting.cli list-profiles

# Run a specific backup profile
uv run python -m backup_after_decrypting.cli run-backup my-profile

# Run all backups that are ready (haven't run in 24 hours)
uv run python -m backup_after_decrypting.cli run-ready

# Run backups ready after custom hours threshold
uv run python -m backup_after_decrypting.cli run-ready --hours 48
```

## Development

### Install Dev Dependencies

```bash
uv sync
```

This installs all dependencies and dev tools (pytest, ruff, mypy).

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Show print statements during tests
uv run pytest -s
```

### Code Quality

```bash
# Lint code
uv run ruff check backup_after_decrypting tests

# Type check
uv run mypy backup_after_decrypting
```

## Project Structure

```
backup-after-decrypting/
├── .gitignore
├── pyproject.toml
├── README.md
├── backup_after_decrypting/
│   ├── __init__.py
│   ├── cli.py
│   └── backup.py
└── tests/
    └── __init__.py

```

## Features

- **Type hints**: Full type annotations for better IDE support and mypy compatibility
- **Backup profile management**: YAML-based configuration for backup profiles
- **CLI interface**: Command-line tool for managing and running backups
- **Testing**: Comprehensive test suite with pytest
- **Code quality**: Automated linting with ruff and type checking with mypy

## Python Best Practices Used

- ✅ **Type hints**: All functions and classes use type annotations
- ✅ **Docstrings**: Clear descriptions of modules, classes, and functions
- ✅ **Project structure**: Proper package layout with separation of concerns
- ✅ **Testing**: Comprehensive test coverage with pytest
- ✅ **Linting**: Code quality checks with ruff
- ✅ **Dependency management**: Explicit dependencies in pyproject.toml
- ✅ **Python versions**: Supports Python 3.10+

## License

MIT

## Contributing

This is a template repository. Feel free to use it as a starting point for your own projects.

## Author

AlexAndrewsAI <alex.andrews.ai@protonmail.com>