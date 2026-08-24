"""holoscrape main entry point.

Polls configured indexers for live streams and dispatches scrapers for
each new stream. Supports two backends:
  - tmux (default): each scraper runs in its own tmux pane
  - subprocess (--no-tmux): each scraper runs as a child process

Usage:
    python main.py              # tmux mode (default)
    python main.py --no-tmux    # subprocess mode (for systemd, etc.)
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import Optional

from modules import config
from modules.indexer.holodex import HolodexIndexer
from modules.logger.base import createLogger
from modules.utils import now
from modules.writer.database import DatabaseWriter
from modules.writer.filesystem import FilesystemWriter


def build_indexers(cfg: config.ConfigHandler) -> list:
    """Instantiate indexers from the configuration."""
    indexers = []
    for ic in cfg.indexers:
        if ic.type == "holodex":
            indexers.append(HolodexIndexer(cfg, ic))
        else:
            print(f"Warning: unknown indexer type '{ic.type}', skipping", file=sys.stderr)
    return indexers


def build_stream_writers(cfg: config.ConfigHandler) -> list:
    """Instantiate writers that handle stream-level events (metadata)."""
    writers = []
    if DatabaseWriter.check_config_enabled(cfg):
        writers.append(DatabaseWriter(cfg, None))
    if FilesystemWriter.check_config_enabled(cfg):
        writers.append(FilesystemWriter(cfg, None))
    return writers


class TmuxManager:
    """Manages scraper processes in tmux panes."""

    def __init__(self) -> None:
        import libtmux
        self._libtmux = libtmux
        self._server = libtmux.Server()
        session = self._server.sessions.get(session_name="holoscrape", default=None)
        if not session:
            session = self._server.new_session("holoscrape", window_name="main.py")
        self._window = session.windows[0]
        self._window.resize(width=220, height=50)
        self._url_to_pane: dict[str, str] = {}

    def is_active(self, url: str) -> bool:
        """Check if a pane for this URL is still alive."""
        pane_id = self._url_to_pane.get(url)
        if pane_id is None:
            return False
        return self._window.panes.get(pane_id=pane_id, default=None) is not None

    def spawn(self, url: str, scrape_path: str) -> bool:
        """Spawn a new tmux pane running the scraper for this URL."""
        try:
            pane = self._window.split(
                shell=f"python3 {scrape_path} {url}"
            )
            self._window.select_layout("tiled")
            self._url_to_pane[url] = pane.pane_id
            return True
        except self._libtmux.exc.LibTmuxException as e:
            return False

    def remove(self, url: str) -> None:
        """Remove tracking for a URL (pane already dead)."""
        self._url_to_pane.pop(url, None)

    def tracked_urls(self) -> list[str]:
        """Return all URLs currently being tracked."""
        return list(self._url_to_pane.keys())

    def kill_all(self) -> None:
        """Kill all scraper panes."""
        for url, pane_id in list(self._url_to_pane.items()):
            try:
                pane = self._window.panes.get(pane_id=pane_id, default=None)
                if pane:
                    pane.kill()
            except Exception:
                pass
        self._url_to_pane.clear()


class SubprocessManager:
    """Manages scraper processes as child subprocesses (no tmux)."""

    def __init__(self) -> None:
        self._url_to_proc: dict[str, subprocess.Popen] = {}

    def is_active(self, url: str) -> bool:
        """Check if the subprocess for this URL is still running."""
        proc = self._url_to_proc.get(url)
        return proc is not None and proc.poll() is None

    def spawn(self, url: str, scrape_path: str) -> bool:
        """Spawn a new subprocess running the scraper for this URL."""
        try:
            proc = subprocess.Popen(
                [sys.executable, scrape_path, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._url_to_proc[url] = proc
            return True
        except OSError:
            return False

    def remove(self, url: str) -> None:
        """Stop tracking a URL (process already dead)."""
        self._url_to_proc.pop(url, None)

    def tracked_urls(self) -> list[str]:
        """Return all URLs currently being tracked."""
        return list(self._url_to_proc.keys())

    def kill_all(self) -> None:
        """Terminate all scraper subprocesses."""
        for url, proc in list(self._url_to_proc.items()):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self._url_to_proc.clear()


def main() -> None:
    parser = argparse.ArgumentParser(description="holoscrape — YouTube live chat scraper")
    parser.add_argument(
        "--no-tmux",
        action="store_true",
        help="Run scrapers as subprocesses instead of tmux panes",
    )
    args = parser.parse_args()

    cfg = config.get_configs()
    errors = cfg.validate()
    if errors:
        for e in errors:
            print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(cfg.log_path, exist_ok=True)
    logger = createLogger(cfg.log_level_enum, None, "main")

    # Build components
    indexers = build_indexers(cfg)
    stream_writers = build_stream_writers(cfg)

    # Create the process manager
    if args.no_tmux:
        manager = SubprocessManager()
        logger.info("Running in subprocess mode (no tmux)")
    else:
        manager = TmuxManager()
        logger.info("Running in tmux mode")

    scrape_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "scrape.py"
    )

    # Signal handling for graceful shutdown
    shutdown = {"requested": False}

    def _signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down")
        shutdown["requested"] = True

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    logger.info(
        f"Started: {len(indexers)} indexer(s), "
        f"poll={cfg.poll_interval}s, max_streams={cfg.max_concurrent_streams}"
    )

    while not shutdown["requested"]:
        # Poll all indexers
        streams: list[dict] = []
        for indexer in indexers:
            try:
                streams += indexer.get_streams()
            except Exception as e:
                logger.error(f"Indexer {type(indexer).__name__} failed: {e}")

        if not streams:
            time.sleep(cfg.poll_interval)
            continue

        # Enforce max concurrent streams
        active_count = sum(1 for s in streams if manager.is_active(s["id"]))
        new_streams = [s for s in streams if not manager.is_active(s["id"])]
        slots_available = cfg.max_concurrent_streams - active_count
        if len(new_streams) > slots_available:
            logger.info(
                f"Max concurrent streams reached ({cfg.max_concurrent_streams}), "
                f"queuing {len(new_streams) - slots_available} stream(s)"
            )
            new_streams = new_streams[:max(0, slots_available)]

        # Write stream metadata
        for stream in streams:
            for w in stream_writers:
                w.process_stream(stream)

        # Detect finished streams (no longer in indexer results)
        urls = [s["id"] for s in streams]
        tracked_urls = manager.tracked_urls()
        for url in tracked_urls:
            if url not in urls:
                logger.info(f"{now()} {url} finished")
                manager.remove(url)
            elif not manager.is_active(url):
                logger.info(f"{now()} {url} pane/process died, will respawn")
                manager.remove(url)

        # Spawn new scrapers
        for stream in new_streams:
            url = stream["id"]
            title = stream.get("title", "")
            channel = stream.get("channel", {}).get("name", "")
            logger.info(f"{now()} {url} started: [{channel}] {title[:60]}")

            if manager.spawn(url, scrape_path):
                logger.info(f"  → scraper launched")
            else:
                logger.error(f"  → failed to launch scraper for {url}")

        time.sleep(cfg.poll_interval)

    # Cleanup
    logger.info("Shutting down...")
    manager.kill_all()
    for w in stream_writers:
        w.finalise()
    logger.info("Done")


if __name__ == "__main__":
    main()
