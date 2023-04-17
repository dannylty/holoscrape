
import requests

from .base import Indexer

class HolodexIndexer(Indexer):
    def get_streams(self):
        if not hasattr(self.configs, 'apikey'):
            return []
        try:
            streams = requests.get("https://holodex.net/api/v2/live?type=placeholder%2Cstream&org=Hololive", headers={"X-APIKEY": self.configs['apikey']}).json()
        except:
            return []

        ret = []

        for stream in streams:
            if stream['type'] == 'placeholder' or stream['status'] != 'live':
                continue

            if 'topic_id' in stream and stream['topic_id'] == 'membersonly':
                continue

            ret.append(stream)

        return ret
