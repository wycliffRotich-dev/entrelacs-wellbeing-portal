from datetime import date

import pytest

from app.config import ConfigError, load_settings


def test_reads_db_password_from_file_and_strips_trailing_newline(make_env):
    assert load_settings(make_env()).db_password == "db-secret-value"


def test_reads_jwt_secret_from_file(make_env):
    assert load_settings(make_env()).jwt_secret == "j" * 64


def test_rejects_plaintext_db_password_in_environment(make_env):
    with pytest.raises(ConfigError, match="DB_PASSWORD"):
        load_settings(make_env(DB_PASSWORD="plaintext"))


def test_rejects_plaintext_jwt_secret_in_environment(make_env):
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        load_settings(make_env(JWT_SECRET="plaintext"))


def test_missing_password_file_variable_fails(make_env):
    env = make_env()
    del env["DB_PASSWORD_FILE"]
    with pytest.raises(ConfigError, match="DB_PASSWORD_FILE"):
        load_settings(env)


def test_unreadable_password_file_path_fails(make_env, tmp_path):
    env = make_env(DB_PASSWORD_FILE=str(tmp_path / "missing"))
    with pytest.raises(ConfigError, match="DB_PASSWORD_FILE"):
        load_settings(env)


def test_empty_password_file_fails(make_env, tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("\n")
    with pytest.raises(ConfigError, match="empty"):
        load_settings(make_env(DB_PASSWORD_FILE=str(empty)))


def test_short_jwt_secret_fails(make_env, tmp_path):
    short = tmp_path / "short"
    short.write_text("too-short")
    with pytest.raises(ConfigError, match="32"):
        load_settings(make_env(JWT_SECRET_FILE=str(short)))


def test_repr_does_not_leak_secrets(make_env):
    text = repr(load_settings(make_env()))
    assert "db-secret-value" not in text
    assert "j" * 64 not in text


def test_reporting_month_defaults_to_october_2026(make_env):
    assert load_settings(make_env()).reporting_month_start == date(2026, 10, 1)
