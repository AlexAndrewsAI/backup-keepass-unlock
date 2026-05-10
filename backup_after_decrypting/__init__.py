"""Python package template.

A simple template for creating Python packages with configuration management.
"""

from backup_after_decrypting.backup import Backup, ConfigBackup, ConfigAllBackups, get_ready_profiles

__version__ = "0.1.0"
__all__ = ["Backup", "ConfigBackup", "ConfigAllBackups", "get_ready_profiles"]
