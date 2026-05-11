"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import typer

from backup_keepass_unlock.backup import (
    load_config_all_backups,
    run_backups,
)

app = typer.Typer(help="Backup after decrypting CLI")


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    profile_name: str = typer.Option(
        None, "--profile", "-p", help="Name of the backup profile to run"
    ),
) -> None:
    """Run a specific backup profile, or all profiles if none is given.

    Args:
        config_path: Path to the backup profiles configuration file.
        profile_name: Name of the backup profile to run (runs all if None)
    """
    try:
        config = load_config_all_backups(config_path)
        if profile_name is not None and profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        run_backups(config, profile_name=profile_name)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except (OSError, ValueError, RuntimeError) as e:
        typer.echo(f"Error running backup: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
