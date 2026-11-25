"""PostgreSQL connections. The password comes from Settings (read from a file), never from env."""
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings

DictConnection = psycopg.Connection[dict[str, Any]]


def connect(settings: Settings) -> DictConnection:
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        row_factory=dict_row,
    )
