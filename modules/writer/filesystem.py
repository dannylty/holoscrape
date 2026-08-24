"""Filesystem writer.

Writes chat messages to plain-text files (one per video) and stream
metadata to JSON files. Files are flushed periodically to balance
throughput against data loss on crash.
"""

import json
import logging
import os
from typing import Any, Optional

from ..config import ConfigHandler
from .base import Writer

FLUSH_INTERVAL = 10  # messages between flushes


class FilesystemWriter(Writer):
    """Writer that persists chat messages to local text files.

    Layout:
        {local_path}/simple/{video_id}.txt   — one line per chat message
        {local_path}/metadata/{video_id}.json — stream metadata (first write wins)
    """

    def __init__(self, configs: ConfigHandler, video_id: Optional[str]) -> None:
        super().__init__(configs, video_id)

        if configs.local_path is None:
            raise ValueError("FilesystemWriter requires local_path in config")

        os.makedirs(os.path.join(configs.local_path, "simple"), exist_ok=True)
        os.makedirs(os.path.join(configs.local_path, "metadata"), exist_ok=True)

        self._file = None
        if video_id:
            path = os.path.join(configs.local_path, "simple", f"{video_id}.txt")
            self._file = open(path, "a", encoding="utf-8")

        self._counter = 0

    @staticmethod
    def check_config_enabled(configs: ConfigHandler) -> bool:
        """Return True if write_to_local is enabled."""
        return getattr(configs, "write_to_local", False)

    def process(self, chat: Any) -> None:
        """Write a chat message to the video's text file."""
        if self._file is None:
            return

        line = f"{self.video_id} {chat.id.replace('%3D', '=')} {chat.datetime} {chat.message}\n"
        self._file.write(line)
        self._counter += 1
        if self._counter >= FLUSH_INTERVAL:
            self._file.flush()
            self._counter = 0

    def process_stream(self, stream: dict[str, Any]) -> None:
        """Write stream metadata as JSON (only if the file doesn't already exist)."""
        if self.configs.local_path is None:
            return

        metadata_path = os.path.join(
            self.configs.local_path, "metadata", f"{stream['id']}.json"
        )
        if not os.path.exists(metadata_path):
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(stream, f, indent=2, ensure_ascii=False)

    def finalise(self) -> None:
        """Flush and close the chat file."""
        if self._file is not None:
            self._file.flush()
            self._file.close()
