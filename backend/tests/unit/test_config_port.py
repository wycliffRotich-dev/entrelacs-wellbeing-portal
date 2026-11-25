import pytest

from app.config import ConfigError, load_settings
from tests.unit.test_config import make_env


def test_default_port_is_5432(tmp_path):
    assert load_settings(make_env(tmp_path)).db_port == 5432


@pytest.mark.parametrize("bad", ["abc", "", "54.32"])
def test_non_integer_port_fails(tmp_path, bad):
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_settings(make_env(tmp_path, DB_PORT=bad))


@pytest.mark.parametrize("bad", ["0", "-1", "65536"])
def test_out_of_range_port_fails(tmp_path, bad):
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_settings(make_env(tmp_path, DB_PORT=bad))
