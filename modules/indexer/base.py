import requests

from modules import config

class Indexer:
    def __init__(self, c: config.ConfigHandler):
        self.configs = c

    def get_streams(self) -> list[str]:
        return []
