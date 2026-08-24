"""Tests for configuration loading and validation."""

import json
import os
import tempfile

import pytest

from modules.config import ConfigHandler, IndexerConfig, get_configs


def _write_config(tmpdir: str, data: dict) -> str:
    path = os.path.join(tmpdir, "config.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestConfigDefaults:
    """Test that missing fields fall back to sensible defaults."""

    def test_minimal_config(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert cfg.write_to_db is False
        assert cfg.write_to_local is True
        assert cfg.poll_interval == 60
        assert cfg.max_concurrent_streams == 10
        assert cfg.log_level == "INFO"
        assert cfg.log_format == "text"

    def test_default_indexers(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert len(cfg.indexers) == 2
        assert cfg.indexers[0].org == "Hololive"
        assert cfg.indexers[1].org == "Nijisanji"
        assert cfg.indexers[1].filter == "EN"

    def test_custom_indexers(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
            "indexers": [
                {"type": "holodex", "org": "Hololive"},
                {"type": "holodex", "org": "Nijisanji", "filter": "EN"},
                {"type": "holodex", "org": "Nijisanji JP", "filter": "JP"},
            ],
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert len(cfg.indexers) == 3
        assert cfg.indexers[2].org == "Nijisanji JP"
        assert cfg.indexers[2].filter == "JP"


class TestConfigValidation:
    """Test that validation catches missing required fields."""

    def test_db_enabled_missing_host(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": True,
            "db_port": 3306,
            "db_user": "user",
            "db_password": "pass",
            "db_database": "db",
            "db_table": "tab",
            "db_stream_table": "stream_tab",
            "write_to_local": False,
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        errors = cfg.validate()
        assert any("db_host" in e for e in errors)

    def test_db_disabled_no_errors(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert cfg.validate() == []

    def test_poll_interval_minimum(self, tmp_path):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
            "poll_interval": 0,
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        errors = cfg.validate()
        assert any("poll_interval" in e for e in errors)


class TestConfigEnvVars:
    """Test environment variable overrides."""

    def test_holodex_apikey_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOLODEX_API_KEY", "test-key-123")
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert cfg.holodex_apikey == "test-key-123"

    def test_db_password_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOLOSCRAPE_DB_PASSWORD", "env-pass")
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": True,
            "db_host": "localhost",
            "db_port": 3306,
            "db_user": "user",
            "db_password": "file-pass",
            "db_database": "db",
            "db_table": "tab",
            "db_stream_table": "stream_tab",
            "write_to_local": False,
            "log_path": str(tmp_path / "logs"),
        })
        cfg = ConfigHandler.from_json_file(cfg_path)
        assert cfg.db_password == "env-pass"  # env overrides file


class TestGetConfigs:
    """Test the get_configs() resolution logic."""

    def test_resolves_from_env(self, tmp_path, monkeypatch):
        cfg_path = _write_config(str(tmp_path), {
            "write_to_db": False,
            "write_to_local": True,
            "local_path": str(tmp_path / "data"),
            "log_path": str(tmp_path / "logs"),
        })
        monkeypatch.setenv("HOLOSCRAPE_CONFIG", cfg_path)
        cfg = get_configs()
        assert cfg.local_path == str(tmp_path / "data")
