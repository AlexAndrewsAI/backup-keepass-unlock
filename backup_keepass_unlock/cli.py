"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import logging

import typer

from backup_keepass_unlock.backup import (
    load_config_all_backups,
    run_backups,
)

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = typer.Typer(help="Backup after decrypting CLI")


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    profile_name: str = typer.Option(
        None, "--profile", "-p", help="Name of the backup profile to run"
    ),
    skip_recent: int | None = typer.Option(
        None, "--skip-recent", "-s", help="Skip backup if less than this many seconds since last run"
    ),
) -> None:
    """Run a specific backup profile, or all profiles if none is given.

    Args:
        config_path: Path to the backup profiles configuration file.
        profile_name: Name of the backup profile to run (runs all if None)
        skip_recent: Skip backup if less than this many seconds since last run (overrides config)
    """
    try:
        config = load_config_all_backups(config_path)
        if profile_name is not None and profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        # Override skip_recent if provided via CLI
        if skip_recent is not None:
            profiles_to_update = (
                [profile_name] if profile_name else config.profiles.keys()
            )
            for profile in profiles_to_update:
                config.profiles[profile].skip_recent = skip_recent

        run_backups(config, profile_name=profile_name)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error running backup: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
