"""End-to-end integration test: Holodex → Scraper → MySQL.

Requires:
    - A running MySQL instance (MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE)
    - A valid Holodex API key (HOLODEX_API_KEY)
    - At least one live Hololive stream at test time

Skips automatically if any prerequisite is missing.
"""

import hashlib
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import mysql.connector

from modules.config import ConfigHandler
from modules.indexer.holodex import HolodexIndexer
from modules.config import IndexerConfig
from scrape import Scraper


def _make_config_file(tmpdir, mysql_host, mysql_port, mysql_user, mysql_password, mysql_database):
    os.makedirs(os.path.join(tmpdir, "logs"), exist_ok=True)
    config_path = os.path.join(tmpdir, "db_config.json")
    config = {
        "write_to_db": True,
        "db_host": mysql_host,
        "db_port": mysql_port,
        "db_user": mysql_user,
        "db_password": mysql_password,
        "db_database": mysql_database,
        "db_table": "example_tab",
        "db_stream_table": "stream_tab",
        "db_nshards": 30,
        "write_to_local": False,
        "log_path": os.path.join(tmpdir, "logs"),
    }
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_path


def _compute_shard(video_id, nshards):
    return int(hashlib.sha1(video_id.encode()).hexdigest()[:8], 16) % nshards


def _create_table_for_shard(cursor, table_name):
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            video_id VARCHAR(255),
            chat_id VARCHAR(255) NOT NULL PRIMARY KEY,
            text VARCHAR(255),
            timestamp VARCHAR(255),
            author_name VARCHAR(255),
            author_id VARCHAR(255),
            source VARCHAR(255)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS stream_tab (
            id VARCHAR(255) NOT NULL PRIMARY KEY,
            title VARCHAR(255),
            topic_id VARCHAR(255),
            channel_id VARCHAR(255),
            channel_name VARCHAR(255)
        )
        """
    )


class MockPytchatVideo:
    """Mock video that yields a fixed number of messages."""

    def __init__(self, video_id, n_messages=150):
        self.video_id = video_id
        self._n_messages = n_messages
        self._msg_idx = 0

    def is_replay(self):
        return False

    def is_alive(self):
        return self._msg_idx < self._n_messages

    def raise_for_status(self):
        if self._msg_idx >= self._n_messages:
            import pytchat
            raise pytchat.ChatDataFinished()

    def get(self):
        items = []
        for _ in range(50):
            if self._msg_idx >= self._n_messages:
                break
            self._msg_idx += 1
            items.append(SimpleNamespace(
                id=f"mock_chat_{self._msg_idx}",
                timestamp=str(1234567890 + self._msg_idx),
                datetime="2026-04-11 12:00:00",
                message=f"mock message {self._msg_idx}",
                author=SimpleNamespace(name="MockUser", channelId="MockChannel"),
            ))
        result = MagicMock()
        result.items = items
        return result


def test_end_to_end_holodex_to_scrape(monkeypatch):
    """Full pipeline: Holodex API → Scraper → MySQL."""
    mysql_host = os.environ.get("MYSQL_HOST")
    ho_api_key = os.environ.get("HOLODEX_API_KEY")
    if not mysql_host or not ho_api_key:
        pytest.skip("MySQL or Holodex API key not configured")

    mysql_port = int(os.environ.get("MYSQL_PORT", 3306))
    mysql_user = os.environ.get("MYSQL_USER", "root")
    mysql_password = os.environ.get("MYSQL_PASSWORD", "")
    mysql_database = os.environ.get("MYSQL_DATABASE", "holoscrape")

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = _make_config_file(
            tmpdir, mysql_host, mysql_port, mysql_user, mysql_password, mysql_database
        )

        monkeypatch.setenv("HOLODEX_API_KEY", ho_api_key)
        monkeypatch.setenv("HOLOSCRAPE_CONFIG", config_path)
        monkeypatch.setattr(
            "scrape.pytchat.create",
            lambda video_id: MockPytchatVideo(video_id, n_messages=150),
        )

        configs = ConfigHandler.from_json_file(config_path)
        indexer = HolodexIndexer(configs, IndexerConfig(org="Hololive"))
        streams = indexer.get_streams()
        if not streams:
            pytest.skip("No live Holodex streams available")

        video_id = streams[0]["id"]
        shard = _compute_shard(video_id, configs.db_nshards)
        table_name = f"{configs.db_table}_{shard}"

        # Set up database
        conn = mysql.connector.connect(
            host=mysql_host, port=mysql_port, user=mysql_user,
            password=mysql_password, database=mysql_database,
        )
        cursor = conn.cursor()
        _create_table_for_shard(cursor, table_name)
        conn.commit()

        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        initial_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        # Run scraper
        scraper = Scraper(video_id, max_messages=150, max_duration_seconds=30)
        scraper.run()

        # Verify
        conn = mysql.connector.connect(
            host=mysql_host, port=mysql_port, user=mysql_user,
            password=mysql_password, database=mysql_database,
        )
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        final_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        assert final_count >= initial_count + 150, (
            f"Expected at least {initial_count + 150} rows, got {final_count}"
        )
