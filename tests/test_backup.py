"""Test suite for backup_keepass_unlock."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from backup_keepass_unlock.backup import (
    ConfigAllBackups,
    ConfigBackup,
    run_backup,
    run_backups,
)
from backup_keepass_unlock.cli import app


@pytest.fixture
def mock_keepass() -> MagicMock:
    """Return a mock KeePass class and instance."""
    mock_kp_class = MagicMock()
    mock_entry = MagicMock()
    mock_entry.get_password.return_value = "secret-password"
    mock_kp_instance = MagicMock()
    mock_kp_instance.find_entries.return_value = [mock_entry]
    mock_kp_class.return_value = mock_kp_instance
    return mock_kp_class


@pytest.fixture
def borg_config(tmp_path: Path) -> ConfigBackup:
    """Return a valid borg backup configuration."""
    out_dir = tmp_path / "borg"
    out_dir.mkdir()
    in_dir = tmp_path / "input"
    in_dir.mkdir()
    must_exist = tmp_path / "must_exist"
    must_exist.write_text("exists")
    return ConfigBackup(
        type="borg",
        title="borg",
        input=[str(in_dir)],
        output=str(out_dir),
        exclude=[],
        must_exist=[str(must_exist)],
    )


class TestConfigBackup:
    """Tests for ConfigBackup model."""

    def test_defaults(self) -> None:
        cfg = ConfigBackup(
            type="borg",
            title="test",
            input=["/a"],
            output="/b",
        )
        assert cfg.exclude == []
        assert cfg.must_exist == []

    def test_full_config(self) -> None:
        cfg = ConfigBackup(
            type="borg",
            title="test",
            input=["/a", "/b"],
            output="/c",
            exclude=["*.tmp"],
            must_exist=["/a"],
        )
        assert cfg.type == "borg"
        assert cfg.title == "test"


class TestConfigAllBackups:
    """Tests for ConfigAllBackups model."""

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        data = {
            "database_path": "/tmp/test.kdbx",
            "profiles": {
                "p1": {
                    "type": "borg",
                    "title": "t1",
                    "input": ["/in"],
                    "output": "/out",
                }
            },
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        cfg = ConfigAllBackups.load(str(path))
        assert cfg.database_path == Path("/tmp/test.kdbx")
        assert "p1" in cfg.profiles
        assert cfg.profiles["p1"].title == "t1"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ConfigAllBackups.load(str(tmp_path / "missing.yml"))

    def test_load_invalid_yaml_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(["not", "a", "mapping"]))
        with pytest.raises(ValueError, match="expected a YAML mapping"):
            ConfigAllBackups.load(str(path))

    def test_load_missing_database_path(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump({"profiles": {}}))
        with pytest.raises(ValueError, match="missing 'database_path'"):
            ConfigAllBackups.load(str(path))

    def test_load_invalid_profiles_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(
            yaml.safe_dump(
                {"database_path": str(tmp_path / "test.kdbx"), "profiles": ["bad"]}
            )
        )
        with pytest.raises(ValueError, match="'profiles' must be a mapping"):
            ConfigAllBackups.load(str(path))


class TestRunBackup:
    """Tests for run_backup function."""

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_success(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = run_backup(
                "test", borg_config, database_path=tmp_path / "test.kdbx"
            )
        assert result is None
        mock_subprocess.assert_called_once()
        call_cmd = mock_subprocess.call_args[0][0]
        assert "borg" in call_cmd
        assert "create" in call_cmd
        archive_args = [a for a in call_cmd if "::" in a]
        assert len(archive_args) == 1
        assert "test_" in archive_args[0]

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_returns_kp(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            kp = run_backup(
                "test",
                borg_config,
                database_path=tmp_path / "test.kdbx",
                return_kp=True,
            )
        assert kp is mock_keepass.return_value

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_uses_provided_kp(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        existing_kp = MagicMock()
        existing_entry = MagicMock()
        existing_entry.get_password.return_value = "existing-password"
        existing_kp.find_entries.return_value = [existing_entry]
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = run_backup(
                "test",
                borg_config,
                database_path=tmp_path / "test.kdbx",
                kp=existing_kp,
                return_kp=True,
            )
        mock_keepass.assert_not_called()
        assert result is existing_kp

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_missing_entry(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_keepass.return_value.find_entries.return_value = []
        mock_subprocess.return_value = MagicMock(returncode=0)
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(ValueError, match="KeePass entry 'borg' not found"),
        ):
            run_backup(
                "test", borg_config, database_path=tmp_path / "test.kdbx"
            )

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_missing_password(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_entry = MagicMock()
        mock_entry.get_password.return_value = None
        mock_keepass.return_value.find_entries.return_value = [mock_entry]
        mock_subprocess.return_value = MagicMock(returncode=0)
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(ValueError, match="Password not found for entry 'borg'"),
        ):
            run_backup(
                "test", borg_config, database_path=tmp_path / "test.kdbx"
            )

    @patch("backup_keepass_unlock.backup.KeePass")
    def test_missing_output_path(
        self, _mock_kp: MagicMock, borg_config: ConfigBackup, tmp_path: Path
    ) -> None:
        borg_config.output = str(tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError, match="does not exist"):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")

    @patch("backup_keepass_unlock.backup.KeePass")
    def test_missing_must_exist_path(
        self, _mock_kp: MagicMock, borg_config: ConfigBackup, tmp_path: Path
    ) -> None:
        borg_config.must_exist = [str(tmp_path / "nonexistent")]
        with pytest.raises(FileNotFoundError, match="does not exist"):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")

    @patch("backup_keepass_unlock.backup.KeePass")
    def test_unknown_backup_type(
        self, _mock_kp: MagicMock, tmp_path: Path
    ) -> None:
        cfg = ConfigBackup(
            type="rsync",
            title="test",
            input=["/in"],
            output=str(tmp_path / "out"),
        )
        (tmp_path / "out").mkdir()
        with pytest.raises(ValueError, match="Unknown backup type"):
            run_backup("test", cfg, database_path=tmp_path / "test.kdbx")

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_borg_failure(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=1)
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(RuntimeError, match="Borg backup failed"),
        ):
            run_backup(
                "test", borg_config, database_path=tmp_path / "test.kdbx"
            )

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_excludes_in_command(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        borg_config.exclude = ["*.tmp", "*.log"]
        mock_subprocess.return_value = MagicMock(returncode=0)
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")
        cmd = mock_subprocess.call_args[0][0]
        assert "--exclude=*.tmp" in cmd
        assert "--exclude=*.log" in cmd

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_borg_passphrase_env(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")
        env = mock_subprocess.call_args[1].get("env")
        assert env is not None
        assert env.get("BORG_PASSPHRASE") == "secret-password"
        assert os.environ.get("BORG_PASSPHRASE") is None


class TestRunBackups:
    """Tests for run_backups function."""

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_all_profiles(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        out = tmp_path / "borg"
        out.mkdir()
        inp = tmp_path / "input"
        inp.mkdir()
        must = tmp_path / "must"
        must.write_text("")
        cfg = ConfigAllBackups(
            database_path=tmp_path / "test.kdbx",
            profiles={
                "p1": ConfigBackup(
                    type="borg", title="borg", input=[str(inp)], output=str(out)
                ),
                "p2": ConfigBackup(
                    type="borg", title="borg", input=[str(inp)], output=str(out)
                ),
            },
        )
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backups(cfg)
        assert mock_subprocess.call_count == 2
        # Verify KeePass instance is reused between profiles
        assert mock_keepass.call_count == 1

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_single_profile(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        out = tmp_path / "borg"
        out.mkdir()
        inp = tmp_path / "input"
        inp.mkdir()
        cfg = ConfigAllBackups(
            database_path=tmp_path / "test.kdbx",
            profiles={
                "p1": ConfigBackup(
                    type="borg", title="borg", input=[str(inp)], output=str(out)
                ),
                "p2": ConfigBackup(
                    type="borg", title="borg", input=[str(inp)], output=str(out)
                ),
            },
        )
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backups(cfg, profile_name="p1")
        assert mock_subprocess.call_count == 1
        mock_keepass.assert_called_once()

    def test_unknown_profile_raises_value_error(self, tmp_path: Path) -> None:
        out = tmp_path / "borg"
        out.mkdir()
        inp = tmp_path / "input"
        inp.mkdir()
        cfg = ConfigAllBackups(
            database_path=tmp_path / "test.kdbx",
            profiles={
                "p1": ConfigBackup(
                    type="borg", title="borg", input=[str(inp)], output=str(out)
                ),
            },
        )
        with pytest.raises(ValueError, match="Profile 'missing' not found"):
            run_backups(cfg, profile_name="missing")


class TestCli:
    """Tests for CLI."""

    runner = CliRunner()

    def test_run_missing_config(self) -> None:
        result = self.runner.invoke(app, ["/nonexistent/config.yml"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_run_invalid_profile(self, tmp_path: Path) -> None:
        data = {
            "database_path": str(tmp_path / "test.kdbx"),
            "profiles": {},
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        result = self.runner.invoke(app, [str(path), "--profile", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_run_success(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        out = tmp_path / "borg"
        out.mkdir()
        inp = tmp_path / "input"
        inp.mkdir()
        data = {
            "database_path": str(tmp_path / "test.kdbx"),
            "profiles": {
                "p1": {
                    "type": "borg",
                    "title": "borg",
                    "input": [str(inp)],
                    "output": str(out),
                }
            },
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = self.runner.invoke(app, [str(path), "--profile", "p1"])
        assert result.exit_code == 0, f"Output: {result.output}"

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_run_all_profiles(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        out = tmp_path / "borg"
        out.mkdir()
        inp = tmp_path / "input"
        inp.mkdir()
        data = {
            "database_path": str(tmp_path / "test.kdbx"),
            "profiles": {
                "p1": {
                    "type": "borg",
                    "title": "borg",
                    "input": [str(inp)],
                    "output": str(out),
                },
                "p2": {
                    "type": "borg",
                    "title": "borg",
                    "input": [str(inp)],
                    "output": str(out),
                },
            },
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = self.runner.invoke(app, [str(path)])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert mock_subprocess.call_count == 2
