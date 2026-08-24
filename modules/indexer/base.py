"""Abstract base class for stream indexers.

An indexer is responsible for discovering currently-live streams and
returning their metadata as a list of dicts.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..config import ConfigHandler


class Indexer(ABC):
    """Base class for all stream indexers."""

    def __init__(self, configs: ConfigHandler) -> None:
        self.configs = configs

    @abstractmethod
    def get_streams(self) -> list[dict[str, Any]]:
        """Return a list of currently-live stream dicts.

        Each dict should contain at minimum:
            - id: YouTube video ID
            - title: Stream title
            - channel: dict with 'id' and 'name'

        Returns an empty list if no streams are found or on error.
        """
        ...
