"""Logging for holoscrape.

Creates per-video log files with rotation support. Each logger gets its own
dedicated handler (no reliance on `logging.basicConfig` which only configures
the root logger once per process).

Supports plain-text and JSON output formats.
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from ..config import get_configs


class _JsonFormatter(logging.Formatter):
    """Formatter that emits each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class BaseLogger:
    """A thin wrapper around a `logging.Logger` with a dedicated file handler.

    Each instance creates its own `RotatingFileHandler` so that multiple
    loggers in the same process write to independent files without
    interfering with each other.
    """

    def __init__(self, level: int, video_id: Optional[str], name: str) -> None:
        self._logger = logging.getLogger(f"{name}.{video_id or 'main'}")
        self._logger.setLevel(level)
        self._logger.propagate = False  # don't leak to root logger

        # Avoid adding duplicate handlers if re-created
        if not self._logger.handlers:
            configs = get_configs()
            os.makedirs(configs.log_path, exist_ok=True)

            if video_id is not None:
                log_file = os.path.join(configs.log_path, f"{video_id}.log")
            else:
                log_file = os.path.join(configs.log_path, "main.log")

            handler = RotatingFileHandler(
                log_file,
                maxBytes=configs.log_max_bytes,
                backupCount=configs.log_backup_count,
                encoding="utf-8",
            )
            handler.setLevel(level)

            if configs.log_format == "json":
                formatter = _JsonFormatter()
            else:
                formatter = logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)

    def exception(self, msg: str) -> None:
        self._logger.exception(msg)


def createLogger(level: int, video_id: Optional[str], name: str) -> BaseLogger:
    """Create a named logger with a dedicated rotating file handler.

    Args:
        level: Logging level (e.g. `logging.INFO`).
        video_id: If set, logs go to `{log_path}/{video_id}.log`.
                  If None, logs go to `{log_path}/main.log`.
        name: Logger name prefix (typically the module name).
    """
    return BaseLogger(level, video_id, name)
