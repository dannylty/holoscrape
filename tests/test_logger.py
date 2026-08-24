"""Tests for the logging module.

Verifies that:
- INFO messages actually appear in the log file (regression test for the
  old basicConfig bug).
- Different video_ids get separate log files.
- Log directory is created if missing.
- JSON format works.
"""

import json
import logging
import os

import pytest

import modules.logger.base as logger_mod
from modules.logger.base import createLogger


class _FakeConfig:
    """Minimal config stub for logger tests."""

    def __init__(self, log_path: str, log_format: str = "text"):
        self.log_path = log_path
        self.log_level = "INFO"
        self.log_format = log_format
        self.log_max_bytes = 10 * 1024 * 1024
        self.log_backup_count = 5


@pytest.fixture
def fake_config(tmp_path, monkeypatch):
    """Patch get_configs to return a config pointing at tmp_path."""
    log_path = str(tmp_path / "logs")

    def _get_configs():
        return _FakeConfig(log_path)

    monkeypatch.setattr(logger_mod, "get_configs", _get_configs)
    return log_path


@pytest.fixture
def fake_config_json(tmp_path, monkeypatch):
    """Patch get_configs for JSON format testing."""
    log_path = str(tmp_path / "logs")

    def _get_configs():
        return _FakeConfig(log_path, log_format="json")

    monkeypatch.setattr(logger_mod, "get_configs", _get_configs)
    return log_path


class TestLogger:
    """Test the BaseLogger / createLogger functionality."""

    def test_info_message_appears_in_file(self, fake_config):
        """Regression: INFO messages must be written to the log file."""
        logger = createLogger(logging.INFO, "testvideo123", "test")
        logger.info("hello info message")

        log_file = os.path.join(fake_config, "testvideo123.log")
        assert os.path.exists(log_file)
        content = open(log_file).read()
        assert "hello info message" in content

    def test_warning_message_appears_in_file(self, fake_config):
        logger = createLogger(logging.INFO, "testvideo456", "test")
        logger.warning("hello warning")

        log_file = os.path.join(fake_config, "testvideo456.log")
        content = open(log_file).read()
        assert "hello warning" in content

    def test_error_message_appears_in_file(self, fake_config):
        logger = createLogger(logging.INFO, "testvideo789", "test")
        logger.error("hello error")

        log_file = os.path.join(fake_config, "testvideo789.log")
        content = open(log_file).read()
        assert "hello error" in content

    def test_separate_files_per_video(self, fake_config):
        """Each video_id gets its own log file."""
        logger1 = createLogger(logging.INFO, "videoAAA", "test")
        logger1.info("message from AAA")

        logger2 = createLogger(logging.INFO, "videoBBB", "test")
        logger2.info("message from BBB")

        file_a = os.path.join(fake_config, "videoAAA.log")
        file_b = os.path.join(fake_config, "videoBBB.log")

        content_a = open(file_a).read()
        content_b = open(file_b).read()

        assert "message from AAA" in content_a
        assert "message from BBB" in content_b
        assert "message from BBB" not in content_a
        assert "message from AAA" not in content_b

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        """Log directory is created if it doesn't exist."""
        log_path = str(tmp_path / "new" / "nested" / "logs")
        assert not os.path.exists(log_path)

        def _get_configs():
            return _FakeConfig(log_path)

        monkeypatch.setattr(logger_mod, "get_configs", _get_configs)

        logger = createLogger(logging.INFO, "videoid", "test")
        logger.info("test")

        assert os.path.exists(log_path)

    def test_main_log_when_no_video_id(self, fake_config):
        """When video_id is None, logs go to main.log."""
        logger = createLogger(logging.INFO, None, "main")
        logger.info("main message")

        log_file = os.path.join(fake_config, "main.log")
        assert os.path.exists(log_file)
        content = open(log_file).read()
        assert "main message" in content

    def test_json_format(self, fake_config_json):
        """JSON log format produces valid JSON lines."""
        logger = createLogger(logging.INFO, "jsonvideo", "test")
        logger.info("json test message")

        log_file = os.path.join(fake_config_json, "jsonvideo.log")
        content = open(log_file).read().strip()
        for line in content.splitlines():
            if line.strip():
                entry = json.loads(line)
                assert "message" in entry
                assert "level" in entry
                assert entry["message"] == "json test message"

    def test_debug_not_logged_at_info_level(self, fake_config):
        """DEBUG messages should not appear when level is INFO."""
        logger = createLogger(logging.INFO, "debugvideo", "test")
        logger.debug("this should not appear")
        logger.info("this should appear")

        log_file = os.path.join(fake_config, "debugvideo.log")
        content = open(log_file).read()
        assert "this should not appear" not in content
        assert "this should appear" in content
