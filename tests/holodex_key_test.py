import os
import pytest
import sys

sys.path.append('..')

from modules.config import get_configs

STUB_API_KEY = "abcdefghijklmnopqrstuv"

def test_holodex_indexer():
    os.environ['HOLODEX_API_KEY'] = STUB_API_KEY
    configs = get_configs()
    assert configs.holodex_apikey == STUB_API_KEY
