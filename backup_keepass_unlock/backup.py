"""Backup module.

Provides backup functionality using borg and KeePass for password management.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from keepass_wrapper.keepass import KeePass  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class ConfigBackup(BaseModel):
    """Configuration for a single backup profile.

    Attributes:
        type: Type of backup (e.g., 'borg').
        title: KeePass entry name for the backup password.
        input: List of paths to backup.
        output: Output path for the backup.
        exclude: List of patterns to exclude from backup.
        must_exist: List of paths that must exist before backup.
    """

    type: str = Field(description="Type of backup (e.g., 'borg')")
    title: str = Field(description="KeePass entry name for the backup password")
    input: list[str] = Field(description="List of paths to backup")
    output: str = Field(description="Output path for the backup")
    exclude: list[str] = Field(
        default_factory=list, description="Patterns to exclude from backup"
    )
    must_exist: list[str] = Field(
        default_factory=list, description="Paths that must exist before backup"
    )
    arguments: list[str] = Field(
        default=["create", "--progress", "--json", "--filter=AME", "-C", "lz4"],
        description="Borg command arguments",
    )
    last_run_file: str = Field(
        default="last_run.dat", description="Filename to store last run timestamp"
    )
    skip_recent: int | None = Field(
        default=None, description="Skip backup if less than this many seconds since last run"
    )

    model_config = {"title": "Backup Config"}


class ConfigAllBackups(BaseModel):
    """Configuration for all backup profiles.

    Attributes:
        database_path: Path to the KeePass database file.
        profiles: Dictionary of profile names to their configurations.
    """

    database_path: Path = Field(description="Path to the KeePass database file")
    profiles: dict[str, ConfigBackup] = Field(
        default_factory=dict, description="Backup profiles"
    )

    model_config = {"title": "All Backups Config"}


def load_config_backup(config_path: str) -> ConfigBackup:
    """Load a single backup profile from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        ConfigBackup instance with loaded configuration.

    Raises:
        FileNotFoundError: If the configuration file is not found.
        ValueError: If the configuration file has invalid format.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup config not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Invalid config format: expected a YAML mapping")
    return ConfigBackup(**data)


def time_since_last_run(config: ConfigBackup) -> float | None:
    """Calculate the time in seconds since the last backup run.

    Args:
        config: Backup configuration containing output path and last_run_file.

    Returns:
        Number of seconds since the last run, or None if the last_run_file
        does not exist.
    """
    last_run_path = Path(config.output) / config.last_run_file
    if not last_run_path.exists():
        return None

    try:
        last_run_str = last_run_path.read_text().strip()
        last_run = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - last_run).total_seconds()
    except (ValueError, OSError) as e:
        logging.warning(f"Failed to parse last_run file: {e}")
        return None


def load_config_all_backups(config_path: str) -> ConfigAllBackups:
    """Load backup profiles from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        ConfigAllBackups instance with loaded profiles.

    Raises:
        FileNotFoundError: If the configuration file is not found.
        ValueError: If the configuration file has invalid format.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup profiles not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Invalid config format: expected a YAML mapping")
    if "database_path" not in data:
        raise ValueError("Invalid config format: missing 'database_path'")
    profiles_data = data.get("profiles", {})
    if not isinstance(profiles_data, dict):
        raise ValueError("Invalid config format: 'profiles' must be a mapping")
    return ConfigAllBackups(
        database_path=data["database_path"],
        profiles={k: ConfigBackup(**v) for k, v in profiles_data.items()},
    )


def run_backup(
    name: str,
    config: str | Path | ConfigBackup,
    database_path: Path,
    kp: KeePass | None = None,
    return_kp: bool = False,
) -> KeePass | None:
    """Run a backup operation.

    Args:
        name: Name of the backup profile.
        config: Backup configuration or path to YAML config file (str or Path).
        database_path: Path to the KeePass database file.
        kp: Optional KeePass instance. If not provided, creates a new one.
        return_kp: If True, returns the KeePass instance for use in other scripts.

    Returns:
        KeePass instance if return_kp is True, otherwise None.
    """
    if isinstance(config, str | Path):
        config = load_config_backup(str(config))
    logging.info(f"Starting backup '{name}'")

    seconds_since_last = time_since_last_run(config)
    if seconds_since_last is not None:
        logging.info(f"Time since last backup: {seconds_since_last:.1f} seconds")
        if config.skip_recent is not None and seconds_since_last < config.skip_recent:
            logging.info(
                f"Skipping backup '{name}' - only {seconds_since_last:.1f} seconds since last run "
                f"(skip_recent threshold: {config.skip_recent} seconds)"
            )
            if return_kp:
                return kp
            return None
    else:
        logging.info("No previous backup run found")

    if kp is None:
        kp = KeePass(database_path=str(database_path))
        logging.info(f"Created new KeePass instance for backup '{name}'")
    else:
        logging.info(f"Using provided KeePass instance for backup '{name}'")

    for path in [config.output, *config.input, *config.must_exist]:
        if not Path(path).exists():
            logging.error(f"Path {path} does not exist")
            raise FileNotFoundError(f"Path {path} does not exist")

    if config.type == "borg":
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_name = f"{name}_{timestamp}"
        cmd = [
            "borg",
            *config.arguments,
            *[f"--exclude={e}" for e in config.exclude],
            f"{config.output}::{archive_name}",
            *config.input,
        ]

        logging.info(f"Running borg backup for '{name}'")
        logging.debug(f"Borg command: {cmd}")

        entries = kp.find_entries(title=config.title, exact=True)
        if not entries:
            logging.error(f"No KeePass entry found for '{config.title}'")
            raise ValueError(f"KeePass entry '{config.title}' not found")
        entry = entries[0]
        logging.debug(f"Found KeePass entry: {entry}")

        password = entry.get_password()
        if password is None:
            logging.error(f"Password not found for entry '{config.title}'")
            raise ValueError(f"Password not found for entry '{config.title}'")

        env = os.environ.copy()
        env["BORG_PASSPHRASE"] = password
        logging.info("Borg passphrase set from KeePass")

        result = subprocess.run(cmd, env=env, text=True)
        if result.returncode != 0:
            logging.error(f"Borg backup failed with exit code {result.returncode}")
            raise RuntimeError(f"Borg backup failed with exit code {result.returncode}")
        logging.info(f"Borg backup completed successfully for '{name}'")
    else:
        logging.error(f"Unknown backup type: {config.type}")
        raise ValueError("Unknown backup type")

    logging.info(f"Backup '{name}' completed successfully")

    # Write current date to last_run_file in output folder
    last_run_path = Path(config.output) / config.last_run_file
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_run_path.write_text(current_date)
    logging.info(f"Updated {config.last_run_file} with: {current_date}")

    if return_kp:
        return kp
    return None


def run_backups(
    config: str | Path | ConfigAllBackups,
    profile_name: str | None = None,
    kp: KeePass | None = None,
    return_kp: bool = False,
) -> KeePass | None:
    """Run backup profiles from a configuration.

    Args:
        config: The loaded backup configuration or path to YAML config (str or Path).
        profile_name: Name of a specific profile to run. If None, all profiles are run.
        kp: Optional KeePass instance. If not provided, creates a new one.
        return_kp: If True, returns the KeePass instance for use in other scripts.

    Returns:
        KeePass instance if return_kp is True, otherwise None.
    """
    if isinstance(config, str | Path):
        config = load_config_all_backups(str(config))
    if profile_name is not None and profile_name not in config.profiles:
        raise ValueError(f"Profile '{profile_name}' not found")
    profiles = (
        {profile_name: config.profiles[profile_name]}
        if profile_name is not None
        else config.profiles
    )
    for name, profile_config in profiles.items():
        kp = run_backup(
            name,
            profile_config,
            database_path=config.database_path,
            kp=kp,
            return_kp=True,
        )
    if return_kp:
        return kp
    return None
