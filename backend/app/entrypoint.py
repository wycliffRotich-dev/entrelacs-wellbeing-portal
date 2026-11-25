"""Production wiring: environment and secret files to a running app (uvicorn --factory)."""
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI

from app.config import load_settings
from app.infrastructure.persistence.connection import DictConnection, connect
from app.infrastructure.security.tokens import TokenService
from app.main import create_app

TOKEN_TTL = timedelta(minutes=30)


def build_app(env: Mapping[str, str]) -> FastAPI:
    settings = load_settings(env)
    month = settings.reporting_month_start

    def connection_factory() -> DictConnection:
        return connect(settings)

    return create_app(
        connection_factory=connection_factory,
        token_service=TokenService(settings.jwt_secret, TOKEN_TTL),
        clock=lambda: datetime.now(UTC),
        reporting_month_start=datetime(month.year, month.month, month.day, tzinfo=UTC),
    )


def create_production_app() -> FastAPI:
    return build_app(os.environ)
