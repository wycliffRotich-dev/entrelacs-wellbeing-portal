from datetime import date

import pytest

from app.config import ConfigError, load_settings


def make_env(tmp_path, **overrides):
    pw = tmp_path / "db_pw"
    pw.write_text("db-secret-value\n")
    jwt = tmp_path / "jwt"
    jwt.write_text("j" * 64 + "\n")
    env = {
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "wellbeing",
        "DB_USER": "wellbeing",
        "DB_PASSWORD_FILE": str(pw),
        "JWT_SECRET_FILE": str(jwt),
    }
    env.update(overrides)
    return env


def test_reads_db_password_from_file_and_strips_trailing_newline(tmp_path):
    settings = load_settings(make_env(tmp_path))
    assert settings.db_password == "db-secret-value"


def test_reads_jwt_secret_from_file(tmp_path):
    settings = load_settings(make_env(tmp_path))
    assert settings.jwt_secret == "j" * 64


def test_rejects_plaintext_db_password_in_environment(tmp_path):
    with pytest.raises(ConfigError, match="DB_PASSWORD"):
        load_settings(make_env(tmp_path, DB_PASSWORD="plaintext"))


def test_rejects_plaintext_jwt_secret_in_environment(tmp_path):
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        load_settings(make_env(tmp_path, JWT_SECRET="plaintext"))


def test_missing_password_file_variable_fails(tmp_path):
    env = make_env(tmp_path)
    del env["DB_PASSWORD_FILE"]
    with pytest.raises(ConfigError, match="DB_PASSWORD_FILE"):
        load_settings(env)


def test_unreadable_password_file_path_fails(tmp_path):
    env = make_env(tmp_path, DB_PASSWORD_FILE=str(tmp_path / "missing"))
    with pytest.raises(ConfigError, match="DB_PASSWORD_FILE"):
        load_settings(env)


def test_empty_password_file_fails(tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("\n")
    with pytest.raises(ConfigError, match="empty"):
        load_settings(make_env(tmp_path, DB_PASSWORD_FILE=str(empty)))


def test_short_jwt_secret_fails(tmp_path):
    short = tmp_path / "short"
    short.write_text("too-short")
    with pytest.raises(ConfigError, match="32"):
        load_settings(make_env(tmp_path, JWT_SECRET_FILE=str(short)))


def test_repr_does_not_leak_secrets(tmp_path):
    text = repr(load_settings(make_env(tmp_path)))
    assert "db-secret-value" not in text
    assert "j" * 64 not in text


def test_reporting_month_defaults_to_october_2026(tmp_path):
    settings = load_settings(make_env(tmp_path))
    assert settings.reporting_month_start == date(2026, 10, 1)
