"""Backup module.

Provides backup functionality using borg and KeePass for password management.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


from keepass_wrapper.keepass import KeePass  # type: ignore[import-untyped]




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
    exclude: list[str] = Field(default_factory=list, description="Patterns to exclude from backup")
    must_exist: list[str] = Field(default_factory=list, description="Paths that must exist before backup")

    model_config = {"title": "Backup Config"}


class ConfigAllBackups(BaseModel):
    """Configuration for all backup profiles.

    Attributes:
        database_path: Path to the KeePass database file.
        profiles: Dictionary of profile names to their configurations.
    """
    database_path: str = Field(description="Path to the KeePass database file")
    profiles: dict[str, ConfigBackup] = Field(default_factory=dict, description="Backup profiles")

    model_config = {"title": "All Backups Config"}

    @classmethod
    def load(cls, config_path: str | None = None) -> "ConfigAllBackups":
        """Load backup profiles from a YAML file.

        Args:
            config_path: Path to the YAML configuration file. If not provided,
                       looks for 'backup_profiles.yaml' in the current directory.

        Returns:
            ConfigAllBackups instance with loaded profiles.

        Raises:
            FileNotFoundError: If the configuration file is not found.
        """
        if config_path is None:
            config_path = "backup_profiles.yaml"
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Backup profiles not found at {path}")
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(
            database_path=data['database_path'],
            profiles={k: ConfigBackup(**v) for k, v in data.get('profiles', {}).items()}
        )



def run_backup(
    name: str,
    config: ConfigBackup,
    database_path: str,
    kp: KeePass | None = None,
    return_kp: bool = False,
) -> KeePass | None:
    """Run a backup operation.

    Args:
        name: Name of the backup profile.
        config: Backup configuration.
        database_path: Path to the KeePass database file.
        kp: Optional KeePass instance. If not provided, creates a new one.
        return_kp: If True, returns the KeePass instance for use in other scripts.

    Returns:
        KeePass instance if return_kp is True, otherwise None.
    """
    logging.info(f"Starting backup '{name}'")

    if kp is None:
        kp = KeePass(database_path=str(database_path))
        logging.info(f"Created new KeePass instance for backup '{name}'")
    else:
        logging.info(f"Using provided KeePass instance for backup '{name}'")

    for path in [config.output] + config.must_exist:
        if not Path(path).exists():
            logging.error(f"Path {path} does not exist")
            raise FileNotFoundError(f"Path {path} does not exist")

    if config.type == "borg":
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_name = f"{name}_{timestamp}"
        cmd = "borg create  --progress  --json --filter=AME -C lz4"
        for e in config.exclude:
            cmd += f' --exclude="{e}"'
        cmd += f' "{config.output}"::{archive_name}'
        for i in config.input:
            cmd += f' "{i}"'

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
        os.environ['BORG_PASSPHRASE'] = password
        logging.info("Borg passphrase set from KeePass")

        result = os.system(cmd)
        os.environ["BORG_PASSPHRASE"] = ""

        if result != 0:
            logging.error(f"Borg backup failed with exit code {result}")
        else:
            logging.info(f"Borg backup completed successfully for '{name}'")
    else:
        logging.error(f"Unknown backup type: {config.type}")
        raise ValueError("Unknown backup type")

    logging.info(f"Backup '{name}' completed successfully")

    if return_kp:
        return kp
    return None
