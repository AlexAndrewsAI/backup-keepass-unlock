"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import typer

from backup_keepass_unlock.backup import run_backup, ConfigAllBackups

app = typer.Typer(help="Backup after decrypting CLI")


@app.command()
def list_profiles(
    config_path: str = typer.Option(None,
        "--config", "-c",
        help="Path to backup profiles YAML file"
    ),
) -> None:
    """List all backup profiles.

    Args:
        config_path: Path to the backup profiles configuration file.
    """
    try:
        config = ConfigAllBackups.load(config_path) if config_path else ConfigAllBackups.load()
        typer.echo(config.model_dump_json(indent=2))
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def run(
    profile_name: str = typer.Argument(..., help="Name of the backup profile to run"),
    config_path: str = typer.Option(None,
        "--config", "-c",
        help="Path to backup profiles YAML file"
    ),
) -> None:
    """Run a specific backup profile.

    Args:
        profile_name: Name of the backup profile to run.
        config_path: Path to the backup profiles configuration file.
    """
    try:
        config = ConfigAllBackups.load(config_path) if config_path else ConfigAllBackups.load()
        if profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        run_backup(profile_name, config.profiles[profile_name], database_path=config.database_path)
        typer.echo(f"Backup '{profile_name}' completed successfully")
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error running backup: {e}", err=True)
        raise typer.Exit(code=1)



if __name__ == "__main__":
    app()
