"""Backup tool using borg and KeePass for password management.
"""

from backup_keepass_unlock.backup import run_backup, ConfigBackup, ConfigAllBackups

__version__ = "0.1.0"
__all__ = ["run_backup", "ConfigBackup", "ConfigAllBackups"]
