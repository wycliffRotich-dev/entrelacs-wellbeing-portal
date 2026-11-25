"""Request-scoped wiring: one DB connection per request, identity always loaded from the DB."""
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.errors import ForbiddenError, NotAuthenticatedError
from app.application.services import AuthService, CheckInService, WellbeingService
from app.domain.users import Role, User
from app.infrastructure.persistence.repositories import PostgresRepository
from app.infrastructure.security.passwords import verify_password
from app.infrastructure.security.tokens import TokenError

_bearer = HTTPBearer(auto_error=False)


def get_repository(request: Request) -> Iterator[PostgresRepository]:
    conn = request.app.state.connection_factory()
    try:
        yield PostgresRepository(conn)
    finally:
        conn.rollback()  # anything not explicitly committed is discarded, locks included
        conn.close()


Repo = Annotated[PostgresRepository, Depends(get_repository)]


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    repo: Repo,
) -> User:
    if credentials is None:
        raise NotAuthenticatedError("missing bearer token")
    clock: Callable[[], datetime] = request.app.state.clock
    try:
        user_id = request.app.state.token_service.verify(credentials.credentials, now=clock())
    except TokenError as exc:
        raise NotAuthenticatedError("invalid token") from exc
    user = repo.get_user(user_id)
    if user is None:
        raise NotAuthenticatedError("unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_employee(user: CurrentUser) -> User:
    if user.role is not Role.EMPLOYEE:
        raise ForbiddenError("employee role required")
    return user


def require_hr(user: CurrentUser) -> User:
    if user.role is not Role.HR:
        raise ForbiddenError("HR role required")
    return user


def get_auth_service(request: Request, repo: Repo) -> AuthService:
    state = request.app.state
    return AuthService(repo, state.token_service, verify_password, state.dummy_hash, state.clock)


def get_check_in_service(request: Request, repo: Repo) -> CheckInService:
    return CheckInService(repo, request.app.state.clock)


def get_wellbeing_service(request: Request, repo: Repo) -> WellbeingService:
    return WellbeingService(repo, request.app.state.reporting_month_start)
