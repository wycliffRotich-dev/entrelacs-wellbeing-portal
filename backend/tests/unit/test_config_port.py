import pytest

from app.config import ConfigError, load_settings


def test_default_port_is_5432(make_env):
    env = make_env()
    del env["DB_PORT"]
    assert load_settings(env).db_port == 5432


@pytest.mark.parametrize("bad", ["abc", "", "54.32"])
def test_non_integer_port_fails(make_env, bad):
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_settings(make_env(DB_PORT=bad))


@pytest.mark.parametrize("bad", ["0", "-1", "65536"])
def test_out_of_range_port_fails(make_env, bad):
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_settings(make_env(DB_PORT=bad))
