from datetime import datetime
import logging
import os
import pytchat
import time
import sys

from modules import config
from modules.logger.base import createLogger
from modules.writer.database import DatabaseWriter
from modules.writer.filesystem import FilesystemWriter

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

class Scraper:
    def __init__(self, video_id, max_messages=None, max_duration_seconds=None):
        self.video_id = video_id
        self.max_messages = max_messages
        self.max_duration_seconds = max_duration_seconds
        self.config = config.get_configs()
        self.logger = createLogger(logging.INFO, video_id, "holoscrape")

        self.writers = []

        if DatabaseWriter.check_config_enabled(self.config):
            self.writers.append(DatabaseWriter(self.config, video_id))

        if FilesystemWriter.check_config_enabled(self.config):
            self.writers.append(FilesystemWriter(self.config, video_id))

        if len(self.writers) <= 0:
            self.logger.error("no writers configured")
            sys.exit(1)

        self.start_time = None

    def should_stop(self, idx):
        if self.max_messages is not None and idx >= self.max_messages:
            return True
        if self.max_duration_seconds is not None and self.start_time is not None and time.time() - self.start_time >= self.max_duration_seconds:
            return True
        return False

    def get_video(self):
        self.video = None
        for attempt in range(5):
            try:
                self.video = pytchat.create(video_id=self.video_id)
                break
            except pytchat.exceptions.InvalidVideoIdException:
                time.sleep(2 ** attempt)
                continue
            except Exception as e:
                self.logger.error(str(e))
                sys.exit(1)
        if self.video is None:
            self.logger.error("can't retrieve video")
            sys.exit(1)

    def run(self):
        self.get_video()

        self.logger.info(f"{now()} {self.video_id} started live scrape")
        
        retries = 0
        idx = 0
        self.start_time = time.time()
        while True:
            if self.video.is_replay(): 
                self.logger.info(f"{now()} {self.video_id} replay detected")
                break

            while self.video.is_alive():
                for c in self.video.get().items:
                    print(self.video_id, idx, c.message)
                    idx += 1

                    for writer in self.writers:
                        writer.process(c)

                    if self.should_stop(idx):
                        break
                
                if self.should_stop(idx):
                    break

                time.sleep(1)

            if self.should_stop(idx):
                break

            try:
                self.video.raise_for_status()

            except pytchat.ChatDataFinished :
                self.logger.info(f"{now()} {self.video} live finished")
                break
                
            except Exception as e:
                if retries < 5:
                    time.sleep(2 ** retries)
                    self.video = pytchat.create(video_id=self.video_id)
                    retries += 1
                    self.logger.warning(f"{now()} {self.video_id} live {type(e)} {str(e)} retrying...")
                    continue

                self.logger.info(f"{now()} {self.video_id} live {type(e)} {str(e)} finished items")
                break

        for writer in self.writers:
            writer.finalise()

if __name__ == "__main__":
    s = Scraper(sys.argv[1])
    try:
        s.run()
    except KeyboardInterrupt:
        print("Cleaning up..")
        for writer in s.writers:
            writer.finalise()