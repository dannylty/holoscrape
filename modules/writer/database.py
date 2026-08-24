"""MySQL database writer.

Buffers chat messages and flushes them in batches to a sharded MySQL table.
The shard is determined by a hash of the video ID.
"""

import hashlib
import logging
from random import randint
from socket import gethostname
from typing import Any, Optional

import mysql.connector

from ..config import ConfigHandler
from .base import Writer


class DatabaseWriter(Writer):
    """Writer that persists chat messages to a sharded MySQL table.

    Batch size is randomised between 30-100 (or a fixed value from config)
    to avoid contention when multiple scraper processes write concurrently.
    """

    def __init__(self, configs: ConfigHandler, video_id: Optional[str]) -> None:
        super().__init__(configs, video_id)
        self._validate(configs)

        self._conn = mysql.connector.connect(
            host=configs.db_host,
            port=configs.db_port,
            user=configs.db_user,
            password=configs.db_password,
            database=configs.db_database,
        )
        self._cursor = self._conn.cursor()

        if video_id:
            self._shard = str(
                int(hashlib.sha1(video_id.encode()).hexdigest()[:8], 16)
                % configs.db_nshards
            )
        else:
            self._shard = None

        self._db_table = configs.db_table
        self._db_stream_table = configs.db_stream_table
        self._batch_size: Optional[int] = configs.db_batch_size
        self._hostname = gethostname()
        self._chat_buffer: list[tuple] = []
        self._next_batch = self._roll_batch()

    def _roll_batch(self) -> int:
        """Determine the next batch size (random or fixed)."""
        if self._batch_size is not None:
            return self._batch_size
        return randint(30, 100)

    def _validate(self, configs: ConfigHandler) -> None:
        """Raise if required DB config fields are missing."""
        required = [
            "db_host", "db_port", "db_user", "db_password",
            "db_database", "db_table", "db_stream_table", "db_nshards",
        ]
        missing = [attr for attr in required if getattr(configs, attr, None) is None]
        if missing:
            raise ValueError(f"DatabaseWriter config missing: {', '.join(missing)}")

    @staticmethod
    def check_config_enabled(configs: ConfigHandler) -> bool:
        """Return True if write_to_db is enabled."""
        return getattr(configs, "write_to_db", False)

    def process(self, chat: Any) -> None:
        """Buffer a chat message; flush when the batch threshold is reached."""
        self._chat_buffer.append((
            self.video_id,
            chat.id.replace("%3D", "="),
            chat.message,
            str(chat.timestamp),
            chat.author.name,
            chat.author.channelId,
            self._hostname,
        ))

        if len(self._chat_buffer) >= self._next_batch:
            self._post()
            self._chat_buffer = []
            self._next_batch = self._roll_batch()

    def process_stream(self, stream: dict[str, Any]) -> None:
        """Insert or replace stream metadata in the stream table."""
        if not self._db_stream_table:
            return
        try:
            query = (
                f"REPLACE INTO {self._db_stream_table} "
                "(id, title, topic_id, channel_id, channel_name) "
                "VALUES(%s, %s, %s, %s, %s)"
            )
            self._cursor.execute(query, (
                stream["id"],
                stream.get("title"),
                stream.get("topic_id"),
                stream.get("channel", {}).get("id"),
                stream.get("channel", {}).get("name"),
            ))
            self._conn.commit()
        except mysql.connector.Error as e:
            self.logger.error(f"Failed to write stream metadata: {e}")

    def _post(self) -> None:
        """Flush the chat buffer to the database."""
        if not self._chat_buffer:
            return

        count = len(self._chat_buffer)
        self.logger.info(f"Posting {count} chats to shard {self._shard}")

        try:
            # Use REPLACE semantics: if chat_id already exists, update source
            # to the current hostname (not append, to avoid unbounded growth).
            query = (
                f"REPLACE INTO {self._db_table}_{self._shard} "
                "(video_id, chat_id, text, timestamp, author_name, author_id, source) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            self._cursor.executemany(query, self._chat_buffer)
            self._conn.commit()
        except mysql.connector.Error as e:
            self.logger.error(f"DB batch insert failed: {e}")
            # Re-raise so the caller can decide whether to retry
            raise

        self.logger.info("Batch posted")

    def finalise(self) -> None:
        """Flush remaining buffer and close the connection."""
        try:
            self._post()
        finally:
            self._cursor.close()
            self._conn.close()
