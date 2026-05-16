"""Test suite for backup_keepass_unlock."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from backup_keepass_unlock.backup import (
    ConfigAllBackups,
    ConfigBackup,
    list_archives,
    load_config_all_backups,
    load_config_backup,
    run_backup,
    run_backups,
    time_since_last_run,
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
        cfg = load_config_all_backups(str(path))
        assert cfg.database_path == Path("/tmp/test.kdbx")
        assert "p1" in cfg.profiles
        assert cfg.profiles["p1"].title == "t1"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config_all_backups(str(tmp_path / "missing.yml"))

    def test_load_invalid_yaml_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(["not", "a", "mapping"]))
        with pytest.raises(ValueError, match="expected a YAML mapping"):
            load_config_all_backups(str(path))

    def test_load_missing_database_path(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump({"profiles": {}}))
        with pytest.raises(ValueError, match="missing 'database_path'"):
            load_config_all_backups(str(path))

    def test_load_invalid_profiles_shape(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yml"
        path.write_text(
            yaml.safe_dump(
                {"database_path": str(tmp_path / "test.kdbx"), "profiles": ["bad"]}
            )
        )
        with pytest.raises(ValueError, match="'profiles' must be a mapping"):
            load_config_all_backups(str(path))


class TestListArchives:
    """Tests for list_archives function."""

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_returns_stdout(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout="archive1  2024-01-01  1.23 GB\n"
        )
        result = list_archives("/repo")
        assert "archive1" in result
        mock_subprocess.assert_called_once_with(
            ["borg", "list", "/repo"], env=None, capture_output=True, text=True
        )

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_empty_repo(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        result = list_archives("/repo")
        assert result == ""

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_passes_env(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        env = {"BORG_PASSPHRASE": "secret"}
        list_archives("/repo", env=env)
        assert mock_subprocess.call_args[1]["env"] == env

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_raises_on_failure(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value = MagicMock(
            returncode=2, stderr="Repository not found", stdout=""
        )
        with pytest.raises(RuntimeError, match="borg list failed"):
            list_archives("/repo")


class TestTimeSinceLastRun:
    """Tests for time_since_last_run function."""

    @patch("backup_keepass_unlock.backup.datetime")
    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_returns_seconds(
        self, mock_subprocess: MagicMock, mock_datetime: MagicMock
    ) -> None:
        # Mock datetime.now() to return a fixed time
        fixed_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = fixed_now
        mock_datetime.strptime = datetime.strptime

        # Mock borg list to return a timestamp from 1 hour ago
        timestamp_str = "2024-01-01_11-00-00"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout=timestamp_str)
        result = time_since_last_run("/repo")
        assert result is not None
        # Should be exactly 3600 seconds (1 hour)
        assert result == 3600
        mock_subprocess.assert_called_once_with(
            [
                "borg",
                "list",
                "--last",
                "1",
                "/repo",
                "--format",
                "{time:%Y-%m-%d_%H-%M-%S}",
            ],
            env=None,
            capture_output=True,
            text=True,
        )

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_no_archives_returns_none(self, mock_subprocess: MagicMock) -> None:
        # Mock borg list to return empty output (no archives)
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        result = time_since_last_run("/repo")
        assert result is None

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_borg_failure_returns_none(self, mock_subprocess: MagicMock) -> None:
        # Mock borg list to fail
        mock_subprocess.return_value = MagicMock(
            returncode=2, stderr="Repository not found", stdout=""
        )
        result = time_since_last_run("/repo")
        assert result is None

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_passes_env(self, mock_subprocess: MagicMock) -> None:
        timestamp = "2024-01-01_00-00-00"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout=timestamp)
        env = {"BORG_PASSPHRASE": "secret"}
        result = time_since_last_run("/repo", env=env)
        assert result is not None
        assert mock_subprocess.call_args[1]["env"] == env

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_invalid_timestamp_returns_none(self, mock_subprocess: MagicMock) -> None:
        # Mock borg list to return invalid timestamp format
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="invalid")
        result = time_since_last_run("/repo")
        assert result is None

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_writes_timestamp_to_file(
        self, mock_subprocess: MagicMock, tmp_path: Path
    ) -> None:
        timestamp = "2024-01-01_00-00-00"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout=timestamp)
        last_run_file = tmp_path / "output" / "last_run.dat"
        result = time_since_last_run("/repo", last_run_file=str(last_run_file))
        assert result is not None
        assert last_run_file.exists()
        assert last_run_file.read_text() == timestamp


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
        # First call: borg create, second call: borg list (to write timestamp)
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = run_backup(
                "test", borg_config, database_path=tmp_path / "test.kdbx"
            )
        assert result is None
        # subprocess called twice: borg create + borg list
        assert mock_subprocess.call_count == 2
        create_cmd = mock_subprocess.call_args_list[0][0][0]
        assert "borg" in create_cmd
        assert "create" in create_cmd
        archive_args = [a for a in create_cmd if "::" in a]
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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(ValueError, match="KeePass entry 'borg' not found"),
        ):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")

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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(ValueError, match="Password not found for entry 'borg'"),
        ):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")

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
    def test_unknown_backup_type(self, _mock_kp: MagicMock, tmp_path: Path) -> None:
        inp = tmp_path / "input"
        inp.mkdir()
        cfg = ConfigBackup(
            type="rsync",
            title="test",
            input=[str(inp)],
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
        # borg create fails (no borg list call since backup fails)
        mock_subprocess.return_value = MagicMock(returncode=1)
        with (
            patch("backup_keepass_unlock.backup.KeePass", mock_keepass),
            pytest.raises(RuntimeError, match="Borg backup failed"),
        ):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_excludes_in_command(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        borg_config.exclude = ["*.tmp", "*.log"]
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")
        create_cmd = mock_subprocess.call_args_list[0][0][0]
        assert "--exclude=*.tmp" in create_cmd
        assert "--exclude=*.log" in create_cmd

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_borg_passphrase_env(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backup("test", borg_config, database_path=tmp_path / "test.kdbx")
        # Both borg list and borg create should receive the passphrase env
        for call in mock_subprocess.call_args_list:
            env = call[1].get("env")
            assert env is not None
            assert env.get("BORG_PASSPHRASE") == "secret-password"
        assert os.environ.get("BORG_PASSPHRASE") is None

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_config_from_path(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        out_dir = tmp_path / "borg"
        out_dir.mkdir()
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        must_exist = tmp_path / "must_exist"
        must_exist.write_text("exists")

        data = {
            "type": "borg",
            "title": "borg",
            "input": [str(in_dir)],
            "output": str(out_dir),
            "exclude": [],
            "must_exist": [str(must_exist)],
        }
        config_path = tmp_path / "config.yml"
        config_path.write_text(yaml.safe_dump(data))

        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backup("test", config_path, database_path=tmp_path / "test.kdbx")
        # borg create + borg list
        assert mock_subprocess.call_count == 2

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_ignore_recent_skips_when_recent(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        # Create the last_run.dat file with a recent timestamp
        last_run_file = tmp_path / "borg" / "last_run.dat"
        last_run_file.parent.mkdir(parents=True, exist_ok=True)
        last_run_file.write_text("2099-01-01_00-00-00")
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = run_backup(
                "test",
                borg_config,
                database_path=tmp_path / "test.kdbx",
                ignore_recent=999999999,
            )
        assert result is None
        # No subprocess calls — backup skipped due to ignore_recent
        assert mock_subprocess.call_count == 0

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_ignore_recent_runs_when_old(
        self,
        mock_subprocess: MagicMock,
        mock_keepass: MagicMock,
        borg_config: ConfigBackup,
        tmp_path: Path,
    ) -> None:
        # Create the last_run.dat file with an old timestamp
        last_run_file = tmp_path / "borg" / "last_run.dat"
        last_run_file.parent.mkdir(parents=True, exist_ok=True)
        last_run_file.write_text("2000-01-01_00-00-00")
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = run_backup(
                "test",
                borg_config,
                database_path=tmp_path / "test.kdbx",
                ignore_recent=1,
            )
        assert result is None
        # borg create + borg list
        assert mock_subprocess.call_count == 2

    def test_load_config_backup_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config_backup(str(tmp_path / "missing.yml"))

    def test_load_config_backup(self, tmp_path: Path) -> None:
        data = {
            "type": "borg",
            "title": "test",
            "input": ["/in"],
            "output": "/out",
            "exclude": ["*.tmp"],
            "must_exist": ["/in"],
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        cfg = load_config_backup(str(path))
        assert cfg.type == "borg"
        assert cfg.title == "test"
        assert cfg.input == ["/in"]
        assert cfg.output == "/out"
        assert cfg.exclude == ["*.tmp"]
        assert cfg.must_exist == ["/in"]


class TestRunBackups:
    """Tests for run_backups function."""

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_all_profiles(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
        # 2 profiles x (borg create + borg list) = 4 calls
        assert mock_subprocess.call_count == 4
        # Verify KeePass instance is reused between profiles
        assert mock_keepass.call_count == 1

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_single_profile(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
        # 1 profile x (borg create + borg list) = 2 calls
        assert mock_subprocess.call_count == 2
        mock_keepass.assert_called_once()

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_ignore_recent_skips_profile(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        # Create the last_run.dat file with a recent timestamp
        out = tmp_path / "borg"
        out.mkdir()
        last_run_file = out / "last_run.dat"
        last_run_file.write_text("2099-01-01_00-00-00")
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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backups(cfg, ignore_recent=999999999)
        # No subprocess calls — backup skipped due to ignore_recent
        assert mock_subprocess.call_count == 0

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

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_config_from_path(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
        config_path = tmp_path / "config.yml"
        config_path.write_text(yaml.safe_dump(data))
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            run_backups(config_path)
        # borg create + borg list
        assert mock_subprocess.call_count == 2


class TestCli:
    """Tests for CLI."""

    runner = CliRunner()

    def test_run_missing_config(self) -> None:
        result = self.runner.invoke(app, ["run", "/nonexistent/config.yml"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_run_invalid_profile(self, tmp_path: Path) -> None:
        data = {
            "database_path": str(tmp_path / "test.kdbx"),
            "profiles": {},
        }
        path = tmp_path / "config.yml"
        path.write_text(yaml.safe_dump(data))
        result = self.runner.invoke(app, ["run", str(path), "--profile", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_run_success(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
            result = self.runner.invoke(app, ["run", str(path), "--profile", "p1"])
        assert result.exit_code == 0, f"Output: {result.output}"

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_run_all_profiles(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
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
            result = self.runner.invoke(app, ["run", str(path)])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert mock_subprocess.call_count == 4

    @patch("backup_keepass_unlock.backup.subprocess.run")
    def test_ignore_recent_cli_skips(
        self, mock_subprocess: MagicMock, mock_keepass: MagicMock, tmp_path: Path
    ) -> None:
        out = tmp_path / "borg"
        out.mkdir()
        # Create the last_run.dat file with a recent timestamp
        last_run_file = out / "last_run.dat"
        last_run_file.write_text("2099-01-01_00-00-00")
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
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
        with patch("backup_keepass_unlock.backup.KeePass", mock_keepass):
            result = self.runner.invoke(
                app,
                ["run", str(path), "--profile", "p1", "--ignore-recent", "999999999"],
            )
        assert result.exit_code == 0, f"Output: {result.output}"
        # No subprocess calls — backup skipped due to ignore_recent
        assert mock_subprocess.call_count == 0
