from datetime import datetime
import logging
import os
import pytchat
import time
from socket import gethostname
import sys
import threading

import config
from writer.database import DatabaseWriter
from writer.filesystem import FilesystemWriter

def now():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S")

class Scraper:
    def __init__(self, video_id):
        self.video_id = video_id
        self.config = config.get_configs()
        self.writers = []

        if DatabaseWriter.check_config_enabled(self.config):
            self.writers.append(DatabaseWriter(self.config, video_id))

        if FilesystemWriter.check_config_enabled(self.config):
            self.writers.append(FilesystemWriter(self.config, video_id))

        if len(self.writers) <= 0:
            logging.error("no writers configured")
            quit()
    
    def get_video(self):
        self.video = None
        for tries in range(5):
            try:
                self.video = pytchat.create(video_id=self.video_id)
                break
            except pytchat.exceptions.InvalidVideoIdException:
                continue
            except Exception as e:
                logging.error(str(e))
                quit()
        if self.video is None:
            logging.error("can't retrieve video")
            quit()

    def run(self):
        self.get_video()

        logging.info(f"{now()} {self.video_id} started live scrape\n")
        
        retries = 0
        while True:
            if self.video.is_replay(): 
                logging.write(f"{now()} {self.video_id} replay detected\n")
                break

            while self.video.is_alive():
                for c in self.video.get().items:
                    print(self.video_id, c.id.replace('%3D', '=')[-10:], c.message)

                    for writer in self.writers:
                        writer.process(c)
                
                time.sleep(1)

            try:
                self.video.raise_for_status()

            except pytchat.ChatDataFinished :
                logging.info(f"{now()} {self.video} live finished\n")
                break
                
            except Exception as e:
                if retries < 5:
                    chat = pytchat.create(video_id=self.video_id)
                    retries += 1
                    log.write(f"{now()} {self.video_id} live {type(e)} {str(e)} retrying...\n")
                    continue

                log.write(f"{now()} {self.video_id} live {type(e)} {str(e)} finished items\n")
                break

        for writer in self.writers:
            writer.finalise()

if __name__ == "__main__":
    s = Scraper(sys.argv[1])
    s.run()