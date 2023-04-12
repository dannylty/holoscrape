import sys

sys.path.append('..')

from modules.config import get_configs

def test_get_configs():
    configs = get_configs()
    assert configs is not None