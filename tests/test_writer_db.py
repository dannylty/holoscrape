"""Tests for the DatabaseWriter (MySQL mocked)."""

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import modules.logger.base as logger_mod
from modules.config import ConfigHandler
from modules.writer.database import DatabaseWriter


class _FakeConfig:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.log_level = "INFO"
        self.log_format = "text"
        self.log_max_bytes = 10 * 1024 * 1024
        self.log_backup_count = 5


@pytest.fixture
def fake_log_config(tmp_path, monkeypatch):
    log_path = str(tmp_path / "logs")
    os.makedirs(log_path, exist_ok=True)
    monkeypatch.setattr(logger_mod, "get_configs", lambda: _FakeConfig(log_path))
    return log_path


import os


def _make_db_config(tmp_path, monkeypatch, **overrides) -> ConfigHandler:
    import json
    config_data = {
        "write_to_db": True,
        "db_host": "localhost",
        "db_port": 3306,
        "db_user": "test",
        "db_password": "test",
        "db_database": "testdb",
        "db_table": "chat_tab",
        "db_stream_table": "stream_tab",
        "db_nshards": 30,
        "write_to_local": False,
        "log_path": str(tmp_path / "logs"),
    }
    config_data.update(overrides)
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return ConfigHandler.from_json_file(config_path)


def _make_chat(chat_id="chat123", message="hello"):
    chat = MagicMock()
    chat.id = chat_id
    chat.datetime = "2026-04-11 12:00:00"
    chat.message = message
    chat.timestamp = "1234567890"
    chat.author = SimpleNamespace(name="TestUser", channelId="UC123")
    return chat


def _compute_shard(video_id: str, nshards: int) -> int:
    return int(hashlib.sha1(video_id.encode()).hexdigest()[:8], 16) % nshards


class TestDatabaseWriter:
    """Test the DatabaseWriter with mocked MySQL connector."""

    @patch("modules.writer.database.mysql.connector.connect")
    def test_init_connects(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        writer = DatabaseWriter(cfg, "testvideo")
        mock_connect.assert_called_once()
        kwargs = mock_connect.call_args[1]
        assert kwargs["host"] == "localhost"
        assert kwargs["database"] == "testdb"

    @patch("modules.writer.database.mysql.connector.connect")
    def test_shard_computation(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        writer = DatabaseWriter(cfg, "testvideo")
        expected_shard = str(_compute_shard("testvideo", 30))
        assert writer._shard == expected_shard

    @patch("modules.writer.database.mysql.connector.connect")
    def test_process_buffers_message(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        # Set a high batch size so we don't trigger a flush
        cfg.db_batch_size = 1000
        writer = DatabaseWriter(cfg, "testvideo")

        writer.process(_make_chat(chat_id="c1", message="first"))
        writer.process(_make_chat(chat_id="c2", message="second"))

        assert len(writer._chat_buffer) == 2
        # executemany should not have been called
        writer._cursor.executemany.assert_not_called()

    @patch("modules.writer.database.mysql.connector.connect")
    def test_process_flushes_at_batch_size(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        cfg.db_batch_size = 3
        writer = DatabaseWriter(cfg, "testvideo")

        writer.process(_make_chat(chat_id="c1"))
        writer.process(_make_chat(chat_id="c2"))
        writer.process(_make_chat(chat_id="c3"))  # triggers flush

        writer._cursor.executemany.assert_called_once()
        assert len(writer._chat_buffer) == 0  # buffer cleared

    @patch("modules.writer.database.mysql.connector.connect")
    def test_process_stream_inserts(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        writer = DatabaseWriter(cfg, None)

        stream = {
            "id": "vid123",
            "title": "Test",
            "topic_id": "topic1",
            "channel": {"id": "ch1", "name": "TestTuber"},
        }
        writer.process_stream(stream)

        writer._cursor.execute.assert_called_once()
        call_args = writer._cursor.execute.call_args
        assert "REPLACE INTO stream_tab" in call_args[0][0]
        writer._conn.commit.assert_called_once()

    @patch("modules.writer.database.mysql.connector.connect")
    def test_finalise_flushes_and_closes(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_db_config(tmp_path, monkeypatch)
        cfg.db_batch_size = 1000
        writer = DatabaseWriter(cfg, "testvideo")

        writer.process(_make_chat(chat_id="c1"))
        writer.finalise()

        # Should have flushed the remaining buffer
        writer._cursor.executemany.assert_called_once()
        writer._cursor.close.assert_called_once()
        writer._conn.close.assert_called_once()

    @patch("modules.writer.database.mysql.connector.connect")
    def test_replaces_not_appends_source(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        """Verify we use REPLACE (not INSERT ... ON DUPLICATE KEY UPDATE CONCAT)."""
        cfg = _make_db_config(tmp_path, monkeypatch)
        cfg.db_batch_size = 1
        writer = DatabaseWriter(cfg, "testvideo")

        writer.process(_make_chat(chat_id="c1"))  # triggers immediate flush

        call_args = writer._cursor.executemany.call_args
        query = call_args[0][0]
        assert "REPLACE INTO" in query
        assert "CONCAT" not in query  # no unbounded growth

    @patch("modules.writer.database.mysql.connector.connect")
    def test_missing_config_raises(self, mock_connect, tmp_path, monkeypatch, fake_log_config):
        import json
        config_data = {
            "write_to_db": True,
            "db_host": "localhost",
            "db_port": 3306,
            "db_user": "test",
            "db_password": "test",
            "db_database": "testdb",
            # missing db_table, db_stream_table
            "write_to_local": False,
            "log_path": str(tmp_path / "logs"),
        }
        config_path = str(tmp_path / "config.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        cfg = ConfigHandler.from_json_file(config_path)

        with pytest.raises(ValueError, match="db_table"):
            DatabaseWriter(cfg, "testvideo")
