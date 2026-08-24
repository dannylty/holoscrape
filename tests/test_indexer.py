"""Tests for the Holodex indexer (HTTP mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.config import ConfigHandler, IndexerConfig
from modules.indexer.holodex import HolodexIndexer

MOCK_STREAMS = [
    {
        "id": "abc123",
        "type": "stream",
        "status": "live",
        "title": "Test Stream",
        "channel": {"id": "ch1", "name": "TestTuber EN"},
        "topic_id": None,
    },
    {
        "id": "def456",
        "type": "placeholder",
        "status": "live",
        "title": "Placeholder",
        "channel": {"id": "ch2", "name": "Another EN"},
    },
    {
        "id": "ghi789",
        "type": "stream",
        "status": "scheduled",
        "title": "Scheduled Stream",
        "channel": {"id": "ch3", "name": "Third EN"},
    },
    {
        "id": "jkl012",
        "type": "stream",
        "status": "live",
        "title": "Members Only",
        "channel": {"id": "ch4", "name": "Fourth EN"},
        "topic_id": "membersonly",
    },
    {
        "id": "mno345",
        "type": "stream",
        "status": "live",
        "title": "JP Stream",
        "channel": {"id": "ch5", "name": "第五チューバー"},
    },
]


def _make_config(tmp_path, **kwargs) -> ConfigHandler:
    import os
    config_data = {
        "write_to_db": False,
        "write_to_local": True,
        "local_path": str(tmp_path / "data"),
        "log_path": str(tmp_path / "logs"),
    }
    config_data.update(kwargs)
    config_path = os.path.join(str(tmp_path), "config.json")
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return ConfigHandler.from_json_file(config_path)


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.json.return_value = data
    resp.status_code = status_code
    resp.raise_for_status.return_value = None
    return resp


class TestHolodexIndexer:
    """Test the unified Holodex indexer with mocked HTTP."""

    def test_no_apikey_returns_empty(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = None
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))
        assert indexer.get_streams() == []

    def test_filters_placeholders(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response(MOCK_STREAMS)
            streams = indexer.get_streams()

        ids = [s["id"] for s in streams]
        assert "def456" not in ids  # placeholder filtered

    def test_filters_non_live(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response(MOCK_STREAMS)
            streams = indexer.get_streams()

        ids = [s["id"] for s in streams]
        assert "ghi789" not in ids  # scheduled filtered

    def test_filters_membersonly(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response(MOCK_STREAMS)
            streams = indexer.get_streams()

        ids = [s["id"] for s in streams]
        assert "jkl012" not in ids  # members only filtered

    def test_no_name_filter_returns_all_live(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response(MOCK_STREAMS)
            streams = indexer.get_streams()

        # abc123 (live, not placeholder, not members-only) + mno345 (live, JP)
        ids = [s["id"] for s in streams]
        assert "abc123" in ids
        assert "mno345" in ids
        assert len(streams) == 2

    def test_name_filter_en(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Nijisanji", filter="EN"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response(MOCK_STREAMS)
            streams = indexer.get_streams()

        # Only abc123 has "EN" in channel name
        ids = [s["id"] for s in streams]
        assert "abc123" in ids
        assert "mno345" not in ids  # JP name doesn't contain "EN"

    def test_request_timeout_used(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            indexer.get_streams()
            # Verify timeout was passed
            call_kwargs = mock_get.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 15

    def test_request_exception_returns_empty(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("timeout")
            streams = indexer.get_streams()

        assert streams == []

    def test_http_error_returns_empty(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Hololive"))

        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = resp
            streams = indexer.get_streams()

        assert streams == []

    def test_correct_org_in_params(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.holodex_apikey = "test-key"
        indexer = HolodexIndexer(cfg, IndexerConfig(org="Nijisanji"))

        with patch("modules.indexer.holodex.requests.get") as mock_get:
            mock_get.return_value = _mock_response([])
            indexer.get_streams()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"]["org"] == "Nijisanji"
