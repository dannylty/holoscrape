"""Configuration loading and validation for holoscrape.

Reads a JSON config file (path resolved from $HOLOSCRAPE_CONFIG, CWD, or
project root) and supplements with environment variables. All optional
fields have sensible defaults so a minimal config still works.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


@dataclass
class IndexerConfig:
    """Configuration for a single indexer instance."""
    type: str = "holodex"
    org: str = "Hololive"
    filter: Optional[str] = None  # e.g. "EN" to filter by channel name substring


@dataclass
class ConfigHandler:
    """Parsed and validated application configuration."""

    # Writers
    write_to_db: bool = False
    write_to_local: bool = True

    # Database
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_database: Optional[str] = None
    db_table: Optional[str] = None
    db_stream_table: Optional[str] = None
    db_nshards: int = 30
    db_batch_size: Optional[int] = None  # None = random(30,100) for contention avoidance

    # Filesystem
    local_path: Optional[str] = None

    # Logging
    log_path: str = "./logs/"
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5

    # Polling / streaming
    poll_interval: int = 60
    max_concurrent_streams: int = 10

    # Indexers (empty = default: Hololive + Nijisanji EN)
    indexers: list[IndexerConfig] = field(default_factory=list)

    # API keys (from env)
    holodex_apikey: Optional[str] = None

    def __post_init__(self) -> None:
        """Apply defaults for indexer list if not specified."""
        if not self.indexers:
            self.indexers = [
                IndexerConfig(type="holodex", org="Hololive"),
                IndexerConfig(type="holodex", org="Nijisanji", filter="EN"),
            ]

    @property
    def log_level_enum(self) -> int:
        """Return the logging level as an integer."""
        return getattr(logging, self.log_level.upper(), logging.INFO)

    @classmethod
    def from_json_file(cls, json_file_path: str) -> "ConfigHandler":
        """Load configuration from a JSON file and environment variables."""
        with open(json_file_path, "r") as f:
            data = json.load(f)

        cfg = cls()

        # Writers
        cfg.write_to_db = data.get("write_to_db", False)
        if cfg.write_to_db:
            cfg.db_host = data.get("db_host")
            cfg.db_port = data.get("db_port")
            cfg.db_user = data.get("db_user")
            cfg.db_password = data.get("db_password")
            cfg.db_database = data.get("db_database")
            cfg.db_table = data.get("db_table")
            cfg.db_stream_table = data.get("db_stream_table")
            cfg.db_nshards = data.get("db_nshards", 30)
            cfg.db_batch_size = data.get("db_batch_size", None)

        cfg.write_to_local = data.get("write_to_local", True)
        if cfg.write_to_local:
            cfg.local_path = data.get("local_path", "./data/")

        # Logging
        cfg.log_path = data.get("log_path", "./logs/")
        cfg.log_level = data.get("log_level", "INFO")
        cfg.log_format = data.get("log_format", "text")
        cfg.log_max_bytes = data.get("log_max_bytes", 10 * 1024 * 1024)
        cfg.log_backup_count = data.get("log_backup_count", 5)

        # Polling
        cfg.poll_interval = data.get("poll_interval", 60)
        cfg.max_concurrent_streams = data.get("max_concurrent_streams", 10)

        # Indexers
        raw_indexers = data.get("indexers", None)
        if raw_indexers:
            cfg.indexers = [
                IndexerConfig(
                    type=entry.get("type", "holodex"),
                    org=entry.get("org", "Hololive"),
                    filter=entry.get("filter", None),
                )
                for entry in raw_indexers
            ]

        # Environment variable overrides
        cfg._parse_envvars()

        return cfg

    def _parse_envvars(self) -> None:
        """Read secrets and overrides from environment variables."""
        holodex_key = os.getenv("HOLODEX_API_KEY")
        if holodex_key:
            self.holodex_apikey = holodex_key

        db_password = os.getenv("HOLOSCRAPE_DB_PASSWORD")
        if db_password:
            self.db_password = db_password

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[str] = []

        if self.write_to_db:
            required = [
                ("db_host", self.db_host),
                ("db_port", self.db_port),
                ("db_user", self.db_user),
                ("db_password", self.db_password),
                ("db_database", self.db_database),
                ("db_table", self.db_table),
                ("db_stream_table", self.db_stream_table),
            ]
            for name, value in required:
                if value is None:
                    errors.append(f"db config missing: {name} (required when write_to_db=true)")

        if self.write_to_local and self.local_path is None:
            errors.append("local_path missing (required when write_to_local=true)")

        if self.poll_interval < 1:
            errors.append(f"poll_interval must be >= 1, got {self.poll_interval}")

        if self.max_concurrent_streams < 1:
            errors.append(f"max_concurrent_streams must be >= 1, got {self.max_concurrent_streams}")

        return errors


def _resolve_config_path() -> str:
    """Resolve the config file path from env var, CWD, or project root."""
    override = os.getenv("HOLOSCRAPE_CONFIG")
    if override:
        return override

    cwd_path = "config.json"
    if os.path.exists(cwd_path):
        return cwd_path

    return os.path.join(_PROJECT_ROOT, "config.json")


def get_configs() -> ConfigHandler:
    """Load and return the application configuration."""
    return ConfigHandler.from_json_file(_resolve_config_path())
