import pytest
import sys

sys.path.append('..')

from modules.config import get_configs
from modules.indexer.holodex import HolodexIndexer

def test_holodex_indexer():
    configs = get_configs()
    indexer = HolodexIndexer(configs)
    streams = indexer.get_streams()
    assert isinstance(streams, list)
    # if no API key is configured, should return empty list gracefully
    if not hasattr(configs, 'holodex_apikey'):
        assert streams == []