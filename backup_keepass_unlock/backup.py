"""Backup module.

Provides backup functionality using borg and KeePass for password management.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict

import yaml
from pydantic import BaseModel, Field


from keepass_wrapper.keepass import KeePass  # type: ignore[import-untyped]




class ConfigBackup(BaseModel):
    """Configuration for a single backup profile.

    Attributes:
        type: Type of backup (e.g., 'borg').
        pw_entry: KeePass entry name for the backup password.
        input: List of paths to backup.
        output: Output path for the backup.
        exclude: List of patterns to exclude from backup.
        mount: List of mount points to check.
        prescript: Command to run before backing up.
        must_exist: List of paths that must exist before backup.
        postscript: Command to run after backing up.
    """
    type: str = Field(description="Type of backup (e.g., 'borg')")
    pw_entry: str = Field(description="KeePass entry name for the backup password")
    input: List[str] = Field(description="List of paths to backup")
    output: str = Field(description="Output path for the backup")
    exclude: List[str] = Field(default_factory=list, description="Patterns to exclude from backup")
    mount: List[str] = Field(default_factory=list, description="Mount points to check")
    prescript: str = Field(default="", description="Command to run before backing up")
    must_exist: List[str] = Field(default_factory=list, description="Paths that must exist before backup")
    postscript: str = Field(default="", description="Command to run after backing up")

    model_config = {"title": "Backup Config"}


class ConfigAllBackups(BaseModel):
    """Configuration for all backup profiles.

    Attributes:
        profiles: Dictionary of profile names to their configurations.
    """
    profiles: Dict[str, ConfigBackup] = Field(default_factory=dict, description="Backup profiles")

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
        return cls(profiles={k: ConfigBackup(**v) for k, v in data.get('profiles', {}).items()})



class Backup:
    """Backup execution class.

    Handles the execution of backup operations using borg and KeePass.
    """

    def __init__(self, name: str, config: ConfigBackup, database_path: str, kp=None):
        """Initialize the Backup instance.

        Args:
            name: Name of the backup profile.
            config: Backup configuration.
            database_path: Path to the KeePass database file.
            kp: Optional KeePass instance. If not provided, creates a new one.
        """
        self.config = config
        self.name = name
        self.database_path = database_path

        if kp is None:
            self.kp = KeePass(database_path=str(database_path))
            logging.info(f"Created new KeePass instance for backup '{name}'")
        else:
            logging.info(f"Using provided KeePass instance for backup '{name}'")
            self.kp = kp
 

    def borg(self) -> None:
        """Execute borg backup."""
        cmd = "borg create  --progress  --json --filter=AME -C lz4"
        for e in self.config.exclude:
            cmd += f' --exclude="{e}"'
        cmd += f' "{self.config.output}"::{self.name}'
        for i in self.config.input:
            cmd += f' "{i}"'
        
        logging.info(f"Running borg backup for '{self.name}'")
        logging.debug(f"Borg command: {cmd}")
        
        entries = self.kp.find_entries(title=self.config.pw_entry, exact=True)
        if not entries:
            logging.error(f"No KeePass entry found for '{self.config.pw_entry}'")
            raise ValueError(f"KeePass entry '{self.config.pw_entry}' not found")
        entry = entries[0]
        logging.debug(f"Found KeePass entry: {entry}")
        
        password = entry.get_password()
        if password is None:
            logging.error(f"Password not found for entry '{self.config.pw_entry}'")
            raise ValueError(f"Password not found for entry '{self.config.pw_entry}'")
        os.environ['BORG_PASSPHRASE'] = password
        logging.info("Borg passphrase set from KeePass")
        
        result = os.system(cmd)
        os.environ["BORG_PASSPHRASE"] = ""
        
        if result != 0:
            logging.error(f"Borg backup failed with exit code {result}")
        else:
            logging.info(f"Borg backup completed successfully for '{self.name}'")


    def run(self) -> None:
        """Run the backup operation.

        Executes prescript, validates paths, runs the backup, and executes postscript.
        """
        logging.info(f"Starting backup '{self.name}'")
        
        if self.config.prescript:
            logging.info(f"Running prescript: {self.config.prescript}")
            os.system(self.config.prescript)

        for path in [self.config.output] + self.config.must_exist:
            if not Path(path).exists():
                logging.error(f"Path {path} does not exist")
                raise FileNotFoundError(f"Path {path} does not exist")
        
        if self.config.type == "borg":
            self.borg()
        else:
            logging.error(f"Unknown backup type: {self.config.type}")
            raise ValueError("Unknown backup type")

        if self.config.postscript:
            logging.info(f"Running postscript: {self.config.postscript}")
            os.system(self.config.postscript)
        
        logging.info(f"Backup '{self.name}' completed successfully")
