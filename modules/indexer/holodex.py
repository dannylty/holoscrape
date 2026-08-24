"""Holodex API indexer.

Queries the Holodex v2 API for live streams, optionally filtering by
organisation and channel name substring. Replaces the previous separate
HolodexIndexer and NijisanjiIndexer classes.
"""

import logging
from typing import Any

import requests

from ..config import ConfigHandler, IndexerConfig
from .base import Indexer

HOLODEX_API_URL = "https://holodex.net/api/v2/live"
REQUEST_TIMEOUT = 15  # seconds


class HolodexIndexer(Indexer):
    """Indexer that queries the Holodex API for live streams.

    Supports filtering by organisation (e.g. "Hololive", "Nijisanji") and
    an optional substring filter on the channel name (e.g. "EN" for
    Nijisanji EN).
    """

    def __init__(self, configs: ConfigHandler, indexer_config: IndexerConfig | None = None) -> None:
        super().__init__(configs)
        self.org = indexer_config.org if indexer_config else "Hololive"
        self.name_filter = indexer_config.filter if indexer_config else None
        self._logger = logging.getLogger(f"holoscrape.indexer.{self.org}")

    def get_streams(self) -> list[dict[str, Any]]:
        """Fetch live streams from the Holodex API.

        Returns an empty list if the API key is missing, the request fails,
        or no matching streams are found.
        """
        apikey = self.configs.holodex_apikey
        if not apikey:
            self._logger.debug("HOLODEX_API_KEY not set, skipping")
            return []

        params = {
            "type": "placeholder,stream",
            "org": self.org,
        }
        headers = {"X-APIKEY": apikey}

        try:
            resp = requests.get(
                HOLODEX_API_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            streams = resp.json()
        except requests.RequestException as e:
            self._logger.warning(f"Holodex API request failed ({self.org}): {e}")
            return []

        return self._filter_streams(streams)

    def _filter_streams(self, streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply filtering rules to the raw API response."""
        result = []
        for stream in streams:
            # Skip placeholders and non-live entries
            if stream.get("type") == "placeholder":
                continue
            if stream.get("status") != "live":
                continue

            # Skip members-only streams
            if stream.get("topic_id") == "membersonly":
                continue

            # Optional channel name filter (e.g. "EN")
            if self.name_filter:
                channel_name = stream.get("channel", {}).get("name", "")
                if self.name_filter not in channel_name:
                    continue

            result.append(stream)

        return result
