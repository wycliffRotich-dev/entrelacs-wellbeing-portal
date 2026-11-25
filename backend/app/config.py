"""Application settings. Secrets are read only from files, never from plain env vars."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MIN_JWT_SECRET_BYTES = 32
FORBIDDEN_PLAINTEXT_VARS = ("DB_PASSWORD", "JWT_SECRET")


class ConfigError(Exception):
    """Raised at startup when configuration is missing or unsafe."""


@dataclass(frozen=True, slots=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    jwt_secret: str = field(repr=False)
    reporting_month_start: date = date(2026, 10, 1)


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _read_secret_file(env: Mapping[str, str], file_var: str) -> str:
    path = _require(env, file_var)
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ConfigError(f"{file_var}: cannot read secret file at {path}") from None
    value = raw.rstrip("\r\n")
    if not value:
        raise ConfigError(f"{file_var} points to an empty file")
    return value


def load_settings(env: Mapping[str, str]) -> Settings:
    for name in FORBIDDEN_PLAINTEXT_VARS:
        if name in env:
            raise ConfigError(f"{name} must not be set; use {name}_FILE instead")
    db_password = _read_secret_file(env, "DB_PASSWORD_FILE")
    jwt_secret = _read_secret_file(env, "JWT_SECRET_FILE")
    if len(jwt_secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
        raise ConfigError(f"JWT_SECRET_FILE: secret must be at least {MIN_JWT_SECRET_BYTES} bytes")
    try:
        port = int(env.get("DB_PORT", "5432"))
    except ValueError:
        raise ConfigError("DB_PORT must be an integer") from None
    if not 1 <= port <= 65535:
        raise ConfigError("DB_PORT must be between 1 and 65535")
    return Settings(
        db_host=_require(env, "DB_HOST"),
        db_port=port,
        db_name=_require(env, "DB_NAME"),
        db_user=_require(env, "DB_USER"),
        db_password=db_password,
        jwt_secret=jwt_secret,
    )
