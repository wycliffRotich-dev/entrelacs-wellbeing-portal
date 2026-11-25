"""Application factory. Every collaborator is injected so tests control the DB, clock and secrets."""
from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI

from app.infrastructure.persistence.connection import DictConnection
from app.infrastructure.security.passwords import hash_password
from app.infrastructure.security.tokens import TokenService
from app.presentation.errors import install_exception_handlers
from app.presentation.routes import router


def create_app(
    *,
    connection_factory: Callable[[], DictConnection],
    token_service: TokenService,
    clock: Callable[[], datetime],
    reporting_month_start: datetime,
) -> FastAPI:
    if reporting_month_start.tzinfo is None:
        raise ValueError("reporting_month_start must be timezone-aware")
    app = FastAPI(title="Entrelacs Wellbeing Portal")
    app.state.connection_factory = connection_factory
    app.state.token_service = token_service
    app.state.clock = clock
    app.state.reporting_month_start = reporting_month_start
    app.state.dummy_hash = hash_password("not-a-real-password")
    install_exception_handlers(app)
    app.include_router(router)
    return app
