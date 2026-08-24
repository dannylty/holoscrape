"""Shared utilities for holoscrape."""

from datetime import datetime


def now() -> str:
    """Return current local time as a human-readable string."""
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")
