"""Application-level errors. Presentation maps them to HTTP; infrastructure may raise them."""


class ApplicationError(Exception):
    """Base class for application-level failures."""


class NotAuthenticatedError(ApplicationError):
    """No valid identity on the request."""


class InvalidCredentialsError(ApplicationError):
    """Login failed. One error for wrong password and unknown email."""


class ForbiddenError(ApplicationError):
    """Authenticated, but the role does not permit this endpoint."""


class NotFoundError(ApplicationError):
    """Resource missing or not visible to the caller. The two are deliberately indistinguishable."""


class ConcurrentDraftError(ApplicationError):
    """Two writers raced to create the same employee's draft."""
