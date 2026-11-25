from pathlib import Path

from tests.db_settings import connect_kwargs

TESTS = Path(__file__).resolve().parents[1]
FORBIDDEN = ("5433", "postgres_password")


def _env(tmp_path, **overrides):
    password_file = tmp_path / "pw"
    password_file.write_text("s3cret\n", encoding="utf-8")
    env = {"TEST_DB_PASSWORD_FILE": str(password_file)}
    env.update(overrides)
    return env


def test_defaults_point_at_the_compose_database(tmp_path):
    assert connect_kwargs("wellbeing_test", _env(tmp_path)) == {
        "host": "127.0.0.1",
        "port": 5433,
        "dbname": "wellbeing_test",
        "user": "wellbeing",
        "password": "s3cret",
    }


def test_environment_overrides_host_and_port(tmp_path):
    kwargs = connect_kwargs(
        "wellbeing_test", _env(tmp_path, TEST_DB_HOST="db.internal", TEST_DB_PORT="6543")
    )
    assert kwargs["host"] == "db.internal"
    assert kwargs["port"] == 6543
    assert kwargs["password"] == "s3cret"


def test_only_the_helper_names_the_default_port_or_the_secret_file():
    skipped = {"db_settings.py", Path(__file__).name}
    offenders = sorted(
        str(path.relative_to(TESTS))
        for path in TESTS.rglob("*.py")
        if path.name not in skipped
        and any(token in path.read_text(encoding="utf-8") for token in FORBIDDEN)
    )
    assert offenders == []
