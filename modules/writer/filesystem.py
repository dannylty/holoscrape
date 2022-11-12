import json
import logging
import os

from modules import config
from .base import Writer

class FilesystemWriter(Writer):
    def __init__(self, c: config.ConfigHandler, video_id: str):
        super().__init__(c, video_id)

        if video_id:
            self.file = open(os.path.join(c.local_path, "simple", video_id + ".txt"), 'a')
        
    def validate_configs(self, c: config.ConfigHandler):
        if not hasattr(c, 'local_path'):
            logging.error("local_path missing")
            return False

        if not os.path.exists(c.local_path):
            logging.error("local_path not a valid directory")
            return False

        return True

    @staticmethod
    def check_config_enabled(c: config.ConfigHandler):
        if not hasattr(c, 'write_to_local'):
            logging.warning('config has no attribute for FilesystemWriter')
            return False
        
        return c.write_to_local

    def process(self, chat):
        self.file.write(f"{self.video_id} {chat.id.replace('%3D', '=')} {chat.datetime} {chat.message}\n")

    def process_stream(self, stream):
        metadata_path = os.path.join(self.configs.local_path, "metadata", stream['id'] + ".txt")
        if not os.path.exists(metadata_path):
            with open(metadata_path, 'a') as f:
                json.dump(stream, f, indent=4, ensure_ascii=False)

    def finalise(self):
        self.file.close()