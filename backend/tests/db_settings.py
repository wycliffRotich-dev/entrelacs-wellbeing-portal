"""Connection settings for the test database, shared by every test that needs it."""
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5433"
USER = "wellbeing"


def connect_kwargs(dbname: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Arguments for psycopg.connect.

    TEST_DB_HOST, TEST_DB_PORT and TEST_DB_PASSWORD_FILE override the defaults, which match
    the Compose database published on 127.0.0.1:5433 with the password in secrets/.
    """
    source = os.environ if env is None else env
    password_file = Path(
        source.get("TEST_DB_PASSWORD_FILE") or ROOT / "secrets" / "postgres_password"
    )
    return {
        "host": source.get("TEST_DB_HOST", DEFAULT_HOST),
        "port": int(source.get("TEST_DB_PORT", DEFAULT_PORT)),
        "dbname": dbname,
        "user": USER,
        "password": password_file.read_text(encoding="utf-8").strip(),
    }
