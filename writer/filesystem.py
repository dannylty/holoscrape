import logging
import os

import config
from .base import Writer

class FilesystemWriter(Writer):
    def __init__(self, config: config.ConfigHandler, video_id: str):
        super().__init__(config, video_id)

        self.file = open(os.path.join(config.local_path, video_id + ".txt"), 'a')
        
    def validate_configs(self, config: config.ConfigHandler):
        if not hasattr(config, 'local_path'):
            logging.error("local_path missing")
            return False

        if not os.path.exists(config.local_path):
            logging.error("local_path not a valid directory")
            return False

        return True

    @staticmethod
    def check_config_enabled(config: config.ConfigHandler):
        if not hasattr(config, 'write_to_local'):
            logging.warning('config has no attribute for FilesystemWriter')
            return False
        
        return config.write_to_local

    def process(self, chat):
        self.file.write(f"{self.video_id} {chat.id.replace('%3D', '=')} {chat.datetime} {chat.message}\n")

    def finalise(self):
        self.file.close()