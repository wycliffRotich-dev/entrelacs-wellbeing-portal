"""Domain rule violations. Presentation maps these to HTTP; the domain knows nothing of HTTP."""


class DomainError(Exception):
    """Base class for all domain rule violations."""


class InvalidAnswerError(DomainError):
    """An answer is not an integer from 0 through 10."""
