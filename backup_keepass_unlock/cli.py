"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import typer

from backup_keepass_unlock.backup import (
    get_stale_profiles,
    load_config_all_backups,
    read_last_run_timestamp,
    run_backups,
)

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d_%H-%M-%S",
)

app = typer.Typer(help="Backup after decrypting CLI")


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    profile_name: str = typer.Option(
        None, "--profile", "-p", help="Name of the backup profile to run"
    ),
    ignore_recent: int | None = typer.Option(
        None,
        "--ignore-recent",
        "-i",
        help=(
            "Skip backup if less than this many seconds since last run "
            "(overrides config)"
        ),
    ),
) -> None:
    """Run a specific backup profile, or all profiles if none is given.

    Args:
        config_path: Path to the backup profiles configuration file.
        profile_name: Name of the backup profile to run (runs all if None)
        ignore_recent: Skip backup if less than this many seconds since last run
    """
    try:
        config = load_config_all_backups(config_path)
        if profile_name is not None and profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        run_backups(config, profile_name=profile_name, ignore_recent=ignore_recent)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error running backup: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(name="last")
def last_cmd(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    profile_name: str = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile whose last run to show (shows all if omitted)",
    ),
) -> None:
    """Show the time since last backup run.

    Args:
        config_path: Path to the backup profiles configuration file.
        profile_name: Name of the backup profile to show last run for (all if None).
    """
    try:
        config = load_config_all_backups(config_path)
        if profile_name is not None and profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        profiles = (
            {profile_name: config.profiles[profile_name]}
            if profile_name is not None
            else config.profiles
        )

        for name, profile_config in profiles.items():
            # Determine last_run_file path (same logic as in run_backup)
            last_run_file = str(Path(profile_config.output) / "last_run.dat")
            if profile_config.type == "borg" and profile_config.last_run_file:
                last_run_file = profile_config.last_run_file

            last_run_timestamp = read_last_run_timestamp(last_run_file)
            if last_run_timestamp is not None:
                seconds_since = (datetime.now() - last_run_timestamp).total_seconds()
                typer.echo(f"=== {name} ===")
                typer.echo(f"Time since last backup: {seconds_since:.1f} seconds")
            else:
                typer.echo(f"=== {name} ===")
                typer.echo("Time since last backup: No previous run found")
            typer.echo("")

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error getting last run: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(name="stale")
def stale_cmd(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    cutoff_seconds: int = typer.Option(
        86400,
        "--cutoff",
        "-c",
        help="Cutoff in seconds (default: 86400 = 24 hours)",
    ),
) -> None:
    """Show profiles that haven't been run within the specified time cutoff.

    Args:
        config_path: Path to the backup profiles configuration file.
        cutoff_seconds: Maximum number of seconds since last run.
    """
    try:
        config = load_config_all_backups(config_path)
        stale = get_stale_profiles(config, cutoff_seconds)

        if stale:
            typer.echo(f"Stale profiles (not run in {cutoff_seconds} seconds):")
            for profile in stale:
                typer.echo(f"  - {profile}")
        else:
            typer.echo(f"No stale profiles (all run within {cutoff_seconds} seconds)")

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error checking stale profiles: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
