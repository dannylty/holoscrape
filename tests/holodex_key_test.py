import pytest
from modules.config import get_configs

STUB_API_KEY = "abcdefghijklmnopqrstuv"

def test_holodex_indexer(monkeypatch):
    monkeypatch.setenv('HOLODEX_API_KEY', STUB_API_KEY)
    monkeypatch.setenv('HOLOSCRAPE_CONFIG', 'tests/config.json')
    configs = get_configs()
    assert configs.holodex_apikey == STUB_API_KEY
