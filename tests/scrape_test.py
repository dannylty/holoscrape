import json
import os
import tempfile
from unittest.mock import MagicMock

from modules.writer.filesystem import FilesystemWriter
from modules.config import ConfigHandler

def _make_chat(video_id="testVideoId"):
    chat = MagicMock()
    chat.id = "chatId123"
    chat.datetime = "2026-04-11 12:00:00"
    chat.message = "hello world"
    return chat

def test_filesystem_writer_creates_file_and_writes(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "simple"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        
        config_path = os.path.join(tmpdir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump({"write_to_db": False, "write_to_local": True, "local_path": tmpdir, "log_path": os.path.join(tmpdir, "logs")}, f)
        monkeypatch.setenv('HOLOSCRAPE_CONFIG', config_path)
        config = ConfigHandler(config_path)

        writer = FilesystemWriter(config, "testVideoId")
        writer.process(_make_chat())
        writer.finalise()

        out = os.path.join(tmpdir, "simple", "testVideoId.txt")
        assert os.path.exists(out)
        content = open(out).read()
        assert "testVideoId" in content
        assert "hello world" in content

def test_filesystem_writer_file_closed_after_finalise(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "simple"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        
        config_path = os.path.join(tmpdir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump({"write_to_db": False, "write_to_local": True, "local_path": tmpdir, "log_path": os.path.join(tmpdir, "logs")}, f)
        monkeypatch.setenv('HOLOSCRAPE_CONFIG', config_path)
        config = ConfigHandler(config_path)

        writer = FilesystemWriter(config, "testVideoId")
        writer.finalise()
        assert writer.file.closed
