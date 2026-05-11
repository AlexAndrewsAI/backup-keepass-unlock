# backup-keepass-unlock

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
git clone https://github.com/AlexAndrewsAI/backup-keepass-unlock.git
cd backup-keepass-unlock
uv sync
```

## Usage

### Command Line Interface

The package includes a CLI tool built with **typer**:

```bash
# Run all profiles in a config file
uv run python3 -m backup_keepass_unlock.cli tests/backup.yml

# Run a specific backup profile
uv run python3 -m backup_keepass_unlock.cli tests/backup.yml --profile test2
```

## Development

### Setup Test Environment

Before running tests, initialize the borg repository for testing:

```bash
mkdir -p tests/borg
borg init --encryption=repokey tests/borg
```

When prompted for a password, use: `b1`

### Install Dev Dependencies

```bash
uv sync --dev
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

# Manually run a single test backup profile
uv run python3 -m backup_keepass_unlock.cli tests/backup.yml --profile test-backup
```

### Code Quality

```bash
# Lint code
uv run ruff check backup_keepass_unlock tests

# Type check
uv run mypy backup_keepass_unlock
```

## Project Structure

```
backup-keepass-unlock/
├── .gitignore
├── AGENTS.md
├── pyproject.toml
├── README.md
├── uv.lock
├── backup_keepass_unlock/
│   ├── __init__.py
│   ├── backup.py
│   └── cli.py
└── tests/
    ├── __init__.py
    ├── backup.yml
    ├── borg/
    ├── dir/
    ├── test.kdbx
    └── test_backup.py

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