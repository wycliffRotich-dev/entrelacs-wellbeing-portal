import os
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
SCHEMA = BACKEND / "app" / "infrastructure" / "persistence" / "schema.sql"
TEST_DB = "wellbeing_test"
NEEDS_DATABASE = {"api", "integration"}


def _connect(dbname: str) -> "psycopg.Connection[Any]":
    password_file = Path(
        os.environ.get("TEST_DB_PASSWORD_FILE", ROOT / "secrets" / "postgres_password")
    )
    return psycopg.connect(
        host=os.environ.get("TEST_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("TEST_DB_PORT", "5433")),
        dbname=dbname,
        user="wellbeing",
        password=password_file.read_text(encoding="utf-8").strip(),
        autocommit=True,
    )


def ensure_test_database() -> None:
    """Create the test database and load the schema when either is missing."""
    with _connect("postgres") as admin:
        found = admin.execute(
            "select 1 from pg_database where datname = %s", (TEST_DB,)
        ).fetchone()
        if found is None:
            admin.execute(sql.SQL("create database {}").format(sql.Identifier(TEST_DB)))
    with _connect(TEST_DB) as conn:
        row = conn.execute("select to_regclass('public.organizations')").fetchone()
        if row is None or row[0] is None:
            conn.execute(SCHEMA.read_text(encoding="utf-8"))


def pytest_collection_finish(session: pytest.Session) -> None:
    """Unit-only runs need no database, so only prepare it when such tests are selected."""
    if not any(item.path.parent.name in NEEDS_DATABASE for item in session.items):
        return
    try:
        ensure_test_database()
    except FileNotFoundError:
        pytest.exit("Secrets are missing. Run scripts/gen-secrets.sh first.", returncode=2)
    except psycopg.OperationalError as error:
        pytest.exit(
            f"Postgres is not reachable ({error}). Start it with: docker compose up -d db",
            returncode=2,
        )


@pytest.fixture
def make_env(tmp_path):
    def _make_env(**overrides):
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

    return _make_env
