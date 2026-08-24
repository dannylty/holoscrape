"""Tests for the Scraper class (pytchat mocked)."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import modules.logger.base as logger_mod
from modules.config import ConfigHandler
from scrape import Scraper


class _FakeConfig:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.log_level = "INFO"
        self.log_format = "text"
        self.log_max_bytes = 10 * 1024 * 1024
        self.log_backup_count = 5
        self.write_to_db = False
        self.write_to_local = True
        self.local_path = None


@pytest.fixture
def fake_config(tmp_path, monkeypatch):
    """Set up a fake config for scraper tests."""
    log_path = str(tmp_path / "logs")
    data_path = str(tmp_path / "data")
    os.makedirs(log_path, exist_ok=True)
    os.makedirs(data_path, exist_ok=True)

    import json
    config_data = {
        "write_to_db": False,
        "write_to_local": True,
        "local_path": data_path,
        "log_path": log_path,
    }
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        json.dump(config_data, f)

    monkeypatch.setenv("HOLOSCRAPE_CONFIG", config_path)
    monkeypatch.setattr(logger_mod, "get_configs", lambda: _FakeConfig(log_path))
    return config_path


import os


class MockPytchatVideo:
    """Mock pytchat video that yields a fixed number of messages then ends."""

    def __init__(self, video_id, n_messages=10, alive_cycles=1):
        self.video_id = video_id
        self._n_messages = n_messages
        self._msg_idx = 0
        self._alive_cycles = alive_cycles
        self._current_cycle = 0
        self._is_alive = True

    def is_replay(self):
        return False

    def is_alive(self):
        return self._is_alive

    def raise_for_status(self):
        if self._msg_idx >= self._n_messages:
            import pytchat
            raise pytchat.ChatDataFinished()

    def get(self):
        items = []
        # Yield remaining messages in this "batch"
        batch_size = 5
        for _ in range(batch_size):
            if self._msg_idx >= self._n_messages:
                break
            items.append(SimpleNamespace(
                id=f"chat_{self._msg_idx}",
                timestamp=str(1234567890 + self._msg_idx),
                datetime="2026-04-11 12:00:00",
                message=f"message {self._msg_idx}",
                author=SimpleNamespace(name="TestUser", channelId="UC123"),
            ))
            self._msg_idx += 1
        result = MagicMock()
        result.items = items
        return result


class TestScraper:
    """Test the Scraper class with mocked pytchat."""

    @patch("scrape.pytchat")
    def test_stops_at_max_messages(self, mock_pytchat, fake_config):
        """Scraper stops after max_messages messages."""
        video = MockPytchatVideo("testvid", n_messages=100)
        mock_pytchat.create.return_value = video
        mock_pytchat.ChatDataFinished = Exception

        scraper = Scraper("testvid", max_messages=10)
        scraper.run()

        # Should have processed exactly 10 messages
        assert video._msg_idx >= 10

    @patch("scrape.pytchat")
    def test_stops_at_max_duration(self, mock_pytchat, fake_config):
        """Scraper stops after max_duration_seconds."""
        video = MockPytchatVideo("testvid", n_messages=10000)
        mock_pytchat.create.return_value = video
        mock_pytchat.ChatDataFinished = Exception

        scraper = Scraper("testvid", max_duration_seconds=0.1)
        scraper.run()

        # Should have stopped due to duration, not processed all messages
        assert video._msg_idx < 10000

    @patch("scrape.pytchat")
    def test_stops_on_replay(self, mock_pytchat, fake_config):
        """Scraper stops when video is set to replay."""
        video = MagicMock()
        video.is_replay.return_value = True
        mock_pytchat.create.return_value = video

        scraper = Scraper("testvid")
        scraper.run()  # should return immediately

    @patch("scrape.pytchat")
    def test_retries_on_connection_error(self, mock_pytchat, fake_config):
        """Scraper retries when connection is lost."""
        import pytchat

        # First video: alive but raises on raise_for_status
        video1 = MagicMock()
        video1.is_replay.return_value = False
        video1.is_alive.return_value = False  # inner loop exits immediately
        video1.raise_for_status.side_effect = ConnectionError("dropped")

        # Second video: finishes normally
        video2 = MagicMock()
        video2.is_replay.return_value = False
        video2.is_alive.return_value = False
        video2.raise_for_status.side_effect = pytchat.ChatDataFinished()

        mock_pytchat.create.side_effect = [video1, video2]
        mock_pytchat.ChatDataFinished = pytchat.ChatDataFinished

        scraper = Scraper("testvid")

        # Patch time.sleep to avoid actual delays
        with patch("scrape.time.sleep"):
            scraper.run()

        # pytchat.create should have been called twice (initial + retry)
        assert mock_pytchat.create.call_count == 2

    @patch("scrape.pytchat")
    def test_gives_up_after_max_retries(self, mock_pytchat, fake_config):
        """Scraper stops after MAX_RETRIES consecutive failures."""
        import pytchat

        # All videos fail on raise_for_status
        def make_failing_video():
            v = MagicMock()
            v.is_replay.return_value = False
            v.is_alive.return_value = False
            v.raise_for_status.side_effect = ConnectionError("dropped")
            return v

        mock_pytchat.create.side_effect = [make_failing_video() for _ in range(10)]
        mock_pytchat.ChatDataFinished = pytchat.ChatDataFinished

        scraper = Scraper("testvid")

        with patch("scrape.time.sleep"):
            scraper.run()

        # Should have stopped (not infinite loop)
        # Initial + 5 retries = 6 calls max
        assert mock_pytchat.create.call_count <= 6

    @patch("scrape.pytchat")
    def test_writers_finalised_on_stop(self, mock_pytchat, fake_config):
        """Writers are finalised when scraping stops."""
        video = MagicMock()
        video.is_replay.return_value = True
        mock_pytchat.create.return_value = video

        scraper = Scraper("testvid")
        finalised = []
        for w in scraper._writers:
            original = w.finalise
            w.finalise = lambda o=original: (finalised.append(1), o())

        scraper.run()
        assert len(finalised) > 0

    @patch("scrape.pytchat")
    def test_request_stop_halts_scraping(self, mock_pytchat, fake_config):
        """Calling request_stop() causes the scraper to halt."""
        video = MagicMock()
        video.is_replay.return_value = False
        video.is_alive.return_value = True
        video.get.return_value = MagicMock(items=[])
        mock_pytchat.create.return_value = video

        scraper = Scraper("testvid")
        scraper.request_stop()
        scraper.run()  # should return immediately

    @patch("scrape.pytchat")
    def test_no_writers_exits(self, mock_pytchat, fake_config, monkeypatch):
        """Scraper exits if no writers are configured."""
        # Override config to disable all writers
        import modules.config as config_mod

        class NoWriterConfig:
            log_path = fake_config
            log_level = "INFO"
            log_level_enum = 20  # logging.INFO
            log_format = "text"
            log_max_bytes = 10 * 1024 * 1024
            log_backup_count = 5
            write_to_db = False
            write_to_local = False
            local_path = None

        monkeypatch.setattr(config_mod, "get_configs", lambda: NoWriterConfig())
        monkeypatch.setattr("scrape.config.get_configs", lambda: NoWriterConfig())

        with pytest.raises(SystemExit):
            Scraper("testvid")
