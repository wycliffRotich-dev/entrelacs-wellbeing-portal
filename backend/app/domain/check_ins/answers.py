"""Answer validation. Used for drafts (per answer) and for scoring."""
from app.domain.exceptions.errors import InvalidAnswerError

MIN_ANSWER = 0
MAX_ANSWER = 10


def validate_answer(value: object) -> int:
    # bool is a subclass of int in Python, so it must be rejected explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidAnswerError("answer must be an integer")
    if not MIN_ANSWER <= value <= MAX_ANSWER:
        raise InvalidAnswerError(f"answer must be between {MIN_ANSWER} and {MAX_ANSWER}")
    return value
