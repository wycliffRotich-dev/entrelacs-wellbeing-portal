import psycopg
import pytest

from tests.db_settings import connect_kwargs


@pytest.fixture
def db():
    """Connection to the wellbeing_test database; every test is rolled back."""
    conn = psycopg.connect(**connect_kwargs("wellbeing_test"))
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
