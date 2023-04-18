
import requests

from .base import Indexer

class NijisanjiIndexer(Indexer):
    def get_streams(self):
        if not hasattr(self.configs, 'apikey'):
            return []
        apikey = self.configs.holodex_apikey

        try:
            streams = requests.get("https://holodex.net/api/v2/live?type=placeholder%2Cstream&org=Nijisanji", headers={"X-APIKEY": apikey}).json()
        except:
            return []

        ret = []

        for stream in streams:
            if stream['type'] == 'placeholder' or stream['status'] != 'live':
                continue

            if 'topic_id' in stream and stream['topic_id'] == 'membersonly':
                continue

            if 'EN' in stream['channel']['name']:
                ret.append(stream)

        return ret
