import os
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def db():
    """Connection to the wellbeing_test database; every test is rolled back."""
    password_file = Path(
        os.environ.get("TEST_DB_PASSWORD_FILE", ROOT / "secrets" / "postgres_password")
    )
    conn = psycopg.connect(
        host=os.environ.get("TEST_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("TEST_DB_PORT", "5433")),
        dbname="wellbeing_test",
        user="wellbeing",
        password=password_file.read_text(encoding="utf-8").strip(),
    )
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
