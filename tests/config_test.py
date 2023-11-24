import pytest
import sys

sys.path.append('..')

from modules.config import get_configs

def test_get_configs():
    configs = get_configs()
    assert configs is not None
    assert not configs.write_to_db
    assert configs.write_to_local
    assert configs.local_path == "./test_data/"
    assert configs.log_path == "./test_logs/"
    with pytest.raises(AttributeError):
        assert configs.db_database is None