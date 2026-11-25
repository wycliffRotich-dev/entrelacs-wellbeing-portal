"""Maps domain and application errors to HTTP. One envelope for every error response."""
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.application.errors import (
    ConcurrentDraftError,
    ForbiddenError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    NotFoundError,
)
from app.domain.exceptions.errors import (
    CheckInAlreadySubmittedError,
    IncompleteCheckInError,
    InvalidAnswerError,
)

Handler = Callable[[Request, Exception], Awaitable[Response]]

_MAPPED: dict[type[Exception], tuple[int, str, str]] = {
    NotAuthenticatedError: (401, "not_authenticated", "authentication required"),
    InvalidCredentialsError: (401, "invalid_credentials", "invalid email or password"),
    ForbiddenError: (403, "forbidden", "you do not have access to this resource"),
    NotFoundError: (404, "not_found", "not found"),
    CheckInAlreadySubmittedError: (
        409,
        "check_in_already_submitted",
        "this check-in was already submitted and cannot be changed",
    ),
    ConcurrentDraftError: (409, "concurrent_update", "concurrent update, please retry"),
    IncompleteCheckInError: (
        422,
        "incomplete_check_in",
        "all three answers are required to submit",
    ),
    InvalidAnswerError: (422, "invalid_answer", "answers must be integers from 0 through 10"),
}


def _envelope(
    status: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status, headers=headers)


def _handler(status: int, code: str, message: str) -> Handler:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None

    async def handle(request: Request, exc: Exception) -> Response:
        return _envelope(status, code, message, headers=headers)

    return handle


async def _validation(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    details = [
        {"field": ".".join(str(part) for part in e["loc"]), "message": str(e["msg"])}
        for e in exc.errors()
    ]
    return _envelope(422, "validation_error", "request validation failed", details=details)


async def _http_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    return _envelope(exc.status_code, "http_error", str(exc.detail))


async def _unexpected(request: Request, exc: Exception) -> Response:
    return _envelope(500, "internal_error", "internal server error")


def install_exception_handlers(app: FastAPI) -> None:
    for exc_type, (status, code, message) in _MAPPED.items():
        app.add_exception_handler(exc_type, _handler(status, code, message))
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected)
