"""Backup module.

Provides backup functionality using borg and KeePass for password management.
"""

import logging
import os
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from keepass_wrapper.keepass import KeePass  # type: ignore[import-untyped]
from pydantic import BaseModel, Field




@contextmanager
def managed_keepass(database_path: str) -> Generator[KeePass, None, None]:
    """Context manager for KeePass instances."""
    kp = KeePass(database_path=database_path)
    try:
        yield kp
    finally:
        # Assuming KeePass has a close method. If not, this might need adjustment.
        if hasattr(kp, "close"):
            kp.close()


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
    last_run_file: str | None = Field(
        default=None,
        description="Path to file where last run timestamp should be written",
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


def read_last_run_timestamp(last_run_file: str) -> datetime | None:
    """Read the last run timestamp from a file.

    Args:
        last_run_file: Path to the file containing the last run timestamp.

    Returns:
        datetime of the last run, or None if file doesn't exist or is invalid.
    """
    try:
        last_run_path = Path(last_run_file)
        if not last_run_path.exists():
            return None
        last_run_str = last_run_path.read_text().strip()
        if not last_run_str:
            return None
        return datetime.strptime(last_run_str, "%Y-%m-%d_%H-%M-%S")
    except (ValueError, OSError) as e:
        logging.warning(f"Failed to read last run timestamp from {last_run_file}: {e}")
        return None


def time_since_last_run(
    output: str, env: dict | None = None, last_run_file: str | None = None
) -> float | None:
    """Calculate the time in seconds since the last backup run.

    Uses borg list to retrieve the timestamp of the most recent archive.

    Args:
        output: Path to the borg repository.
        env: Environment variables to pass to borg (should include BORG_PASSPHRASE).
        last_run_file: Path to file where last run timestamp should be written.

    Returns:
        Number of seconds since the last run, or None if no archive exists.
    """
    cmd = [
        "borg",
        "list",
        "--last",
        "1",
        output,
        "--format",
        "{time:%Y-%m-%d_%H-%M-%S}",
    ]
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Borg list command failed for {output}: {result.stderr}")
            return None

        last_run_str = result.stdout.strip()
        if not last_run_str:
            logging.info(f"No archives found in {output}")
            return None

        try:
            last_run = datetime.strptime(last_run_str, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            logging.error(f"Invalid timestamp format returned by borg: {last_run_str}")
            return None

        seconds_since = (datetime.now() - last_run).total_seconds()

        if last_run_file:
            last_run_path = Path(last_run_file)
            last_run_path.parent.mkdir(parents=True, exist_ok=True)
            last_run_path.write_text(last_run_str)
            logging.info(f"Wrote last run timestamp to {last_run_file}")

        return seconds_since
    except OSError as e:
        logging.error(f"System error while running borg list for {output}: {e}")
        return None


def list_archives(output: str, env: dict | None = None) -> str:
    """List all archives in a borg repository.

    Args:
        output: Path to the borg repository.
        env: Environment variables to pass to borg (should include BORG_PASSPHRASE).

    Returns:
        The human-readable output of borg list (name, timestamp, size per line).

    Raises:
        RuntimeError: If the borg list command fails.
    """
    cmd = ["borg", "list", output]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"borg list failed for '{output}': {result.stderr.strip()}")
    return result.stdout


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
    ignore_recent: int | None = None,
) -> KeePass | None:
    """Run a backup operation.

    Args:
        name: Name of the backup profile.
        config: Backup configuration or path to YAML config file (str or Path).
        database_path: Path to the KeePass database file.
        kp: Optional KeePass instance. If not provided, creates a new one.
        return_kp: If True, returns the KeePass instance for use in other scripts.
        ignore_recent: Skip backup if the last run was less than this many seconds
            ago.

    Returns:
        KeePass instance if return_kp is True, otherwise None.
    """
    if isinstance(config, str | Path):
        config = load_config_backup(str(config))
    logging.info(f"Starting backup '{name}'")

    for path in [config.output, *config.input, *config.must_exist]:
        if not Path(path).exists():
            logging.error(f"Path {path} does not exist")
            raise FileNotFoundError(f"Path {path} does not exist")

    last_run_file = str(Path(config.output) / "last_run.dat")
    if config.type == "borg":
        if config.last_run_file:
            last_run_file = config.last_run_file

        # Read last run timestamp from file to determine whether to skip
        last_run_timestamp = read_last_run_timestamp(last_run_file)
        seconds_since_last = None
        if last_run_timestamp is not None:
            seconds_since_last = (datetime.now() - last_run_timestamp).total_seconds()
            logging.info(f"Time since last backup: {seconds_since_last:.1f} seconds")
            threshold = ignore_recent
            if threshold is not None and seconds_since_last < threshold:
                logging.info(
                    f"Skipping backup '{name}' - only {seconds_since_last:.1f} "
                    f"seconds since last run (ignore_recent threshold: {threshold} "
                    f"seconds)"
                )
                if return_kp:
                    return kp
                return None
        else:
            logging.info("No previous backup run found")

    if kp is None:
        with managed_keepass(str(database_path)) as kp_managed:
            kp = kp_managed
            logging.info(f"Created new KeePass instance for backup '{name}'")
            return _execute_backup(name, config, kp, last_run_file, return_kp)
    else:
        logging.info(f"Using provided KeePass instance for backup '{name}'")
        return _execute_backup(name, config, kp, last_run_file, return_kp)


def _execute_backup(
    name: str,
    config: ConfigBackup,
    kp: KeePass,
    last_run_file: str,
    return_kp: bool,
) -> KeePass | None:
    """Internal helper to execute the backup logic with an open KeePass instance."""
    if config.type == "borg":
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

        result = subprocess.run(cmd, env=env, text=True)
        if result.returncode != 0:
            logging.error(f"Borg backup failed with exit code {result.returncode}")
            raise RuntimeError(f"Borg backup failed with exit code {result.returncode}")
        logging.info(f"Borg backup completed successfully for '{name}'")

        # Update last run timestamp file after successful backup
        time_since_last_run(config.output, env=env, last_run_file=last_run_file)
    else:
        logging.error(f"Unknown backup type: {config.type}")
        raise ValueError("Unknown backup type")

    logging.info(f"Backup '{name}' completed successfully")

    if return_kp:
        return kp
    return None


def run_backups(
    config: str | Path | ConfigAllBackups,
    profile_name: str | None = None,
    kp: KeePass | None = None,
    return_kp: bool = False,
    ignore_recent: int | None = None,
) -> KeePass | None:
    """Run backup profiles from a configuration.

    Args:
        config: The loaded backup configuration or path to YAML config (str or Path).
        profile_name: Name of a specific profile to run. If None, all profiles are run.
        kp: Optional KeePass instance. If not provided, creates a new one.
        return_kp: If True, returns the KeePass instance for use in other scripts.
        ignore_recent: Skip any backup whose last run was less than this many seconds
            ago.

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
            ignore_recent=ignore_recent,
        )
    if return_kp:
        return kp
    return None


def get_stale_profiles(
    config: str | Path | ConfigAllBackups, cutoff_seconds: int = 86400
) -> list[str]:
    """Get profiles that haven't been run within the specified time cutoff.

    Args:
        config: The loaded backup configuration or path to YAML config (str or Path).
        cutoff_seconds: Maximum number of seconds since last run. Profiles that haven't
            been run within this time (or have never been run) will be returned.

    Returns:
        List of profile names that are stale (haven't been run within cutoff_seconds).
    """
    if isinstance(config, str | Path):
        config = load_config_all_backups(str(config))

    stale_profiles = []
    for name, profile_config in config.profiles.items():
        last_run_file = str(Path(profile_config.output) / "last_run.dat")
        if profile_config.last_run_file:
            last_run_file = profile_config.last_run_file

        last_run_timestamp = read_last_run_timestamp(last_run_file)
        if last_run_timestamp is None:
            # No last run record - consider it stale
            stale_profiles.append(name)
            continue

        seconds_since = (datetime.now() - last_run_timestamp).total_seconds()
        if seconds_since > cutoff_seconds:
            stale_profiles.append(name)

    return stale_profiles
