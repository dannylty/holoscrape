import os
import sys
import tempfile
from unittest.mock import MagicMock

sys.path.append('..')

from modules.writer.filesystem import FilesystemWriter

def _make_config(local_path, log_path):
    c = MagicMock()
    c.write_to_local = True
    c.local_path = local_path
    c.log_path = log_path
    return c

def _make_chat(video_id="testVideoId"):
    chat = MagicMock()
    chat.id = "chatId123"
    chat.datetime = "2026-04-11 12:00:00"
    chat.message = "hello world"
    return chat

def test_filesystem_writer_creates_file_and_writes():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "simple"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        config = _make_config(tmpdir, os.path.join(tmpdir, "logs"))

        writer = FilesystemWriter(config, "testVideoId")
        writer.process(_make_chat())
        writer.finalise()

        out = os.path.join(tmpdir, "simple", "testVideoId.txt")
        assert os.path.exists(out)
        content = open(out).read()
        assert "testVideoId" in content
        assert "hello world" in content

def test_filesystem_writer_file_closed_after_finalise():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "simple"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        config = _make_config(tmpdir, os.path.join(tmpdir, "logs"))

        writer = FilesystemWriter(config, "testVideoId")
        writer.finalise()
        assert writer.file.closed
