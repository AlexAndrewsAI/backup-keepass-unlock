"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import logging
import os

import typer
from keepass_wrapper.keepass import KeePass  # type: ignore[import-untyped]

from backup_keepass_unlock.backup import (
    load_config_all_backups,
    run_backups,
    time_since_last_run,
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

        kp: KeePass | None = None
        for name, profile_config in profiles.items():
            if kp is None:
                kp = KeePass(database_path=str(config.database_path))

            entries = kp.find_entries(title=profile_config.title, exact=True)
            if not entries:
                typer.echo(
                    f"Error: KeePass entry '{profile_config.title}' not found", err=True
                )
                raise typer.Exit(code=1)

            password = entries[0].get_password()
            if password is None:
                typer.echo(
                    f"Error: Password not found for entry '{profile_config.title}'",
                    err=True,
                )
                raise typer.Exit(code=1)

            env = os.environ.copy()
            env["BORG_PASSPHRASE"] = password

            seconds_since = time_since_last_run(profile_config.output, env=env)
            if seconds_since is not None:
                typer.echo(f"=== {name} ===")
                typer.echo(f"Time since last backup: {seconds_since:.1f} seconds")
            else:
                typer.echo(f"=== {name} ===")
                typer.echo("Time since last backup: No archives found")
            typer.echo("")

    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error getting last run: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
