"""Domain rule violations. Presentation maps these to HTTP; the domain knows nothing of HTTP."""


class DomainError(Exception):
    """Base class for all domain rule violations."""


class InvalidAnswerError(DomainError):
    """An answer is not an integer from 0 through 10."""


class IncompleteCheckInError(DomainError):
    """Submission requires all three answers."""


class CheckInAlreadySubmittedError(DomainError):
    """A submitted check-in is immutable and cannot be changed or submitted again."""


class NaiveDatetimeError(DomainError):
    """A timezone-naive datetime was supplied where an aware one is required."""
