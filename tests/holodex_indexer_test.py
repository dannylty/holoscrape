import pytest
import sys

sys.path.append('..')

from modules.config import get_configs
from modules.indexer.holodex import HolodexIndexer

def test_holodex_indexer():
    configs = get_configs()
    indexer = HolodexIndexer(configs)
    print(len(indexer.get_streams()))