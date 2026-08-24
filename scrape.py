"""Live YouTube chat scraper.

Connects to a live YouTube stream via pytchat and dispatches each chat
message to the configured writers. Handles reconnection with exponential
backoff, and stops cleanly when the stream ends or is set to replay.
"""

import logging
import signal
import sys
import time
from typing import Optional

import pytchat

from modules import config
from modules.logger.base import createLogger
from modules.utils import now
from modules.writer.database import DatabaseWriter
from modules.writer.filesystem import FilesystemWriter

MAX_RETRIES = 5
RETRY_BASE_DELAY = 2  # seconds; actual delay = BASE * 2^retry


class Scraper:
    """Scrapes chat messages from a single live YouTube video.

    Args:
        video_id: YouTube video ID to scrape.
        max_messages: Optional stop condition — stop after N messages.
        max_duration_seconds: Optional stop condition — stop after N seconds.
    """

    def __init__(
        self,
        video_id: str,
        max_messages: Optional[int] = None,
        max_duration_seconds: Optional[float] = None,
    ) -> None:
        self.video_id = video_id
        self.max_messages = max_messages
        self.max_duration_seconds = max_duration_seconds
        self._configs = config.get_configs()
        self.logger = createLogger(
            self._configs.log_level_enum, video_id, "holoscrape"
        )

        self._writers = self._init_writers()
        if not self._writers:
            self.logger.error("No writers configured")
            sys.exit(1)

        self._video: Optional["pytchat.LiveChat"] = None
        self._start_time: Optional[float] = None
        self._stop_requested = False

    def _init_writers(self) -> list:
        """Instantiate all enabled writers."""
        writers = []
        if DatabaseWriter.check_config_enabled(self._configs):
            writers.append(DatabaseWriter(self._configs, self.video_id))
        if FilesystemWriter.check_config_enabled(self._configs):
            writers.append(FilesystemWriter(self._configs, self.video_id))
        return writers

    def request_stop(self) -> None:
        """Signal the scraper to stop gracefully (e.g. from a signal handler)."""
        self.logger.info("Stop requested")
        self._stop_requested = True

    def _should_stop(self, idx: int) -> bool:
        """Check whether any stop condition has been met."""
        if self._stop_requested:
            return True
        if self.max_messages is not None and idx >= self.max_messages:
            return True
        if (
            self.max_duration_seconds is not None
            and self._start_time is not None
            and time.time() - self._start_time >= self.max_duration_seconds
        ):
            return True
        return False

    def _connect(self) -> "pytchat.LiveChat":
        """Connect to the video's chat with retry logic."""
        for attempt in range(5):
            try:
                video = pytchat.create(video_id=self.video_id)
                return video
            except pytchat.exceptions.InvalidVideoIdException:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                self.logger.warning(
                    f"Invalid video ID (attempt {attempt + 1}/5), retrying in {delay}s"
                )
                time.sleep(delay)
            except Exception as e:
                self.logger.error(f"Failed to connect: {type(e).__name__}: {e}")
                raise
        raise ConnectionError(f"Could not connect to video {self.video_id} after 5 attempts")

    def run(self) -> None:
        """Main scraping loop. Blocks until the stream ends or a stop condition is met."""
        self._video = self._connect()
        self.logger.info(f"{now()} {self.video_id} started live scrape")

        retries = 0
        idx = 0
        self._start_time = time.time()

        while not self._stop_requested:
            # Check if the stream has been set to replay (ended)
            if self._video.is_replay():
                self.logger.info(f"{now()} {self.video_id} replay detected (stream ended)")
                break

            # Inner loop: read messages while the chat is alive
            while self._video.is_alive() and not self._stop_requested:
                try:
                    items = self._video.get().items
                except Exception as e:
                    self.logger.warning(f"Error reading chat: {type(e).__name__}: {e}")
                    break

                for c in items:
                    idx += 1
                    for writer in self._writers:
                        writer.process(c)
                    if self._should_stop(idx):
                        break

                if self._should_stop(idx):
                    break

                time.sleep(1)

            if self._should_stop(idx):
                break

            # The inner loop exited (video no longer alive or read error).
            # Determine why and decide whether to retry.
            try:
                self._video.raise_for_status()
            except pytchat.ChatDataFinished:
                self.logger.info(f"{now()} {self.video_id} live finished")
                break
            except Exception as e:
                if retries < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** retries)
                    self.logger.warning(
                        f"{now()} {self.video_id} connection lost "
                        f"({type(e).__name__}: {e}), retry {retries + 1}/{MAX_RETRIES} in {delay}s"
                    )
                    time.sleep(delay)
                    try:
                        self._video = pytchat.create(video_id=self.video_id)
                        retries += 1
                        # Reset retry counter after successful reconnect
                        # (we'll reset it again once we get messages)
                    except Exception as reconnect_err:
                        self.logger.error(f"Reconnect failed: {reconnect_err}")
                        retries = MAX_RETRIES  # force exit
                else:
                    self.logger.error(
                        f"{now()} {self.video_id} max retries reached, giving up"
                    )
                    break

            # Reset retries if we made it through a full cycle without error
            # (i.e. the stream went idle and came back)
            if self._video is not None and self._video.is_alive():
                retries = 0

        self.logger.info(f"{now()} {self.video_id} scrape complete ({idx} messages)")
        for writer in self._writers:
            writer.finalise()


def main() -> None:
    """Entry point for standalone scraper execution."""
    if len(sys.argv) < 2:
        print("Usage: python scrape.py <video_id> [max_messages] [max_duration_s]", file=sys.stderr)
        sys.exit(1)

    video_id = sys.argv[1]
    max_messages = int(sys.argv[2]) if len(sys.argv) > 2 else None
    max_duration = float(sys.argv[3]) if len(sys.argv) > 3 else None

    scraper = Scraper(video_id, max_messages=max_messages, max_duration_seconds=max_duration)

    # Install signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, lambda *_: scraper.request_stop())
    signal.signal(signal.SIGINT, lambda *_: scraper.request_stop())

    try:
        scraper.run()
    except KeyboardInterrupt:
        scraper.request_stop()
        for writer in scraper._writers:
            writer.finalise()


if __name__ == "__main__":
    main()
