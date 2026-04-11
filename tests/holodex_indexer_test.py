import pytest
from modules.config import get_configs
from modules.indexer.holodex import HolodexIndexer

def test_holodex_indexer(monkeypatch):
    monkeypatch.setenv('HOLOSCRAPE_CONFIG', 'tests/config.json')
    configs = get_configs()
    indexer = HolodexIndexer(configs)
    streams = indexer.get_streams()
    assert isinstance(streams, list)
    if not hasattr(configs, 'holodex_apikey'):
        assert streams == []
