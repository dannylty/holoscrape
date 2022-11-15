import logging
import os

from ..config import get_configs

class BaseLogger:
    def __init__(self, level, video_id, name):
        configs = get_configs()
        if video_id is not None:
            log_path = os.path.join(configs.log_path, video_id + ".log")
            with open(log_path, 'a+') as f:
                pass
            logging.basicConfig(filename=log_path, encoding='utf-8', level=logging.INFO)
            self.logger = logging.getLogger(name)

    def debug(self, s):
        self.logger.debug(s)

    def info(self, s):
        self.logger.info(s)

    def warning(self, s):
        self.logger.warning(s)

    def error(self, s):
        self.logger.error(s)

def createLogger(level, video_id, name) -> BaseLogger:
    return BaseLogger(level, video_id, name)