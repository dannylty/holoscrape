import pytest
from modules.config import get_configs

def test_get_configs(monkeypatch):
    monkeypatch.setenv('HOLOSCRAPE_CONFIG', 'tests/config.json')
    configs = get_configs()
    assert configs is not None
    assert not configs.write_to_db
    assert configs.write_to_local
    assert configs.local_path == "./test_data/"
    assert configs.log_path == "./test_logs/"
    with pytest.raises(AttributeError):
        assert configs.db_database is None
