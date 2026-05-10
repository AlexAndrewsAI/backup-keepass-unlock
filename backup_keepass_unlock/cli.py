"""Command line interface module.

Provides a typer-based CLI for the package.
"""

import typer

from backup_keepass_unlock.backup import run_backup, ConfigAllBackups

app = typer.Typer(help="Backup after decrypting CLI")


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to backup profiles YAML file"),
    profile_name: str = typer.Option(None,
        "--profile", "-p",
        help="Name of the backup profile to run"
    ),
) -> None:
    """Run a specific backup profile, or all profiles if none is given.

    Args:
        config_path: Path to the backup profiles configuration file.
        profile_name: Name of the backup profile to run. If not provided, runs all profiles.
    """
    try:
        config = ConfigAllBackups.load(config_path)
        if profile_name is not None and profile_name not in config.profiles:
            typer.echo(f"Error: Profile '{profile_name}' not found", err=True)
            raise typer.Exit(code=1)

        if profile_name is not None:
            run_backup(profile_name, config.profiles[profile_name], database_path=config.database_path)
            typer.echo(f"Backup '{profile_name}' completed successfully")
        else:
            kp = None
            for name, profile_config in config.profiles.items():
                kp = run_backup(name, profile_config, database_path=config.database_path, kp=kp, return_kp=True)
                typer.echo(f"Backup '{name}' completed successfully")
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error running backup: {e}", err=True)
        raise typer.Exit(code=1)



if __name__ == "__main__":
    app()
