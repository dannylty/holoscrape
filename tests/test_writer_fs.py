"""Tests for the FilesystemWriter."""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import modules.logger.base as logger_mod
from modules.config import ConfigHandler
from modules.writer.filesystem import FilesystemWriter


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


def _make_chat(chat_id="chat123", message="hello world", timestamp="1234567890"):
    chat = MagicMock()
    chat.id = chat_id
    chat.datetime = "2026-04-11 12:00:00"
    chat.message = message
    chat.timestamp = timestamp
    chat.author = SimpleNamespace(name="TestUser", channelId="UC123")
    return chat


def _make_config(tmp_path, monkeypatch, **overrides) -> ConfigHandler:
    import json as json_mod
    config_data = {
        "write_to_db": False,
        "write_to_local": True,
        "local_path": str(tmp_path / "data"),
        "log_path": str(tmp_path / "logs"),
    }
    config_data.update(overrides)
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        json_mod.dump(config_data, f)
    return ConfigHandler.from_json_file(config_path)


class TestFilesystemWriter:
    """Test the FilesystemWriter chat and stream processing."""

    def test_creates_file_and_writes(self, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, "testVideoId")
        writer.process(_make_chat())
        writer.finalise()

        out = os.path.join(cfg.local_path, "simple", "testVideoId.txt")
        assert os.path.exists(out)
        content = open(out).read()
        assert "testVideoId" in content
        assert "hello world" in content

    def test_file_closed_after_finalise(self, tmp_path, monkeypatch, fake_log_config):
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, "testVideoId")
        writer.finalise()
        assert writer._file.closed

    def test_flush_every_10_messages(self, tmp_path, monkeypatch, fake_log_config):
        """Verify the flush counter resets after 10 messages."""
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, "testVideoId")

        for i in range(10):
            writer.process(_make_chat(chat_id=f"chat{i}", message=f"msg {i}"))

        # After 10 messages, counter should have reset to 0
        assert writer._counter == 0

    def test_metadata_written_once(self, tmp_path, monkeypatch, fake_log_config):
        """Stream metadata is only written if the file doesn't exist."""
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, None)

        stream = {
            "id": "vid123",
            "title": "Test Stream",
            "channel": {"id": "ch1", "name": "TestTuber"},
        }
        writer.process_stream(stream)

        metadata_path = os.path.join(cfg.local_path, "metadata", "vid123.json")
        assert os.path.exists(metadata_path)
        data = json.load(open(metadata_path))
        assert data["title"] == "Test Stream"

        # Second call should not overwrite
        import time
        time.sleep(0.01)
        stream["title"] = "Updated Title"
        writer.process_stream(stream)
        data2 = json.load(open(metadata_path))
        assert data2["title"] == "Test Stream"  # unchanged

    def test_no_video_id_no_file_created(self, tmp_path, monkeypatch, fake_log_config):
        """Writer with video_id=None doesn't create a chat file."""
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, None)
        assert writer._file is None

        # process() should be a no-op, not crash
        writer.process(_make_chat())
        writer.finalise()

    def test_url_encoded_chat_id_decoded(self, tmp_path, monkeypatch, fake_log_config):
        """%3D in chat IDs is decoded to =."""
        cfg = _make_config(tmp_path, monkeypatch)
        writer = FilesystemWriter(cfg, "testVideoId")
        writer.process(_make_chat(chat_id="abc%3Ddef"))
        writer.finalise()

        out = os.path.join(cfg.local_path, "simple", "testVideoId.txt")
        content = open(out).read()
        assert "abc=def" in content
        assert "%3D" not in content
