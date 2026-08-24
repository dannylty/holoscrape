"""Abstract base class for stream/chat writers.

A writer receives either individual chat messages (`process`) or stream
metadata (`process_stream`) and persists them to some backend.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..config import ConfigHandler
from ..logger.base import createLogger


class Writer(ABC):
    """Base class for all output writers."""

    def __init__(self, configs: ConfigHandler, video_id: Optional[str]) -> None:
        self.configs = configs
        self.video_id = video_id
        self.logger = createLogger(logging.INFO, video_id, self.__class__.__name__)

    @staticmethod
    @abstractmethod
    def check_config_enabled(configs: ConfigHandler) -> bool:
        """Return True if this writer is enabled in the given configuration."""
        ...

    @abstractmethod
    def process(self, chat: Any) -> None:
        """Process a single chat message."""
        ...

    def process_stream(self, stream: dict[str, Any]) -> None:
        """Process stream metadata (called when a new stream is detected).

        Default implementation is a no-op. Override in subclasses that
        need to persist stream-level information.
        """
        pass

    def finalise(self) -> None:
        """Flush and close any open resources. Called when a stream ends."""
        pass
