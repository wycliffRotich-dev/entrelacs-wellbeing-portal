from decimal import Decimal

import pytest

from app.domain.check_ins.score import calculate_score
from app.domain.exceptions.errors import InvalidAnswerError


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ((0, 0, 0), Decimal("0.0")),
        ((10, 10, 10), Decimal("100.0")),
        ((5, 5, 5), Decimal("50.0")),
        ((0, 0, 1), Decimal("3.3")),
        ((10, 10, 9), Decimal("96.7")),
        ((7, 8, 9), Decimal("80.0")),
    ],
)
def test_score_is_mean_times_ten_to_one_decimal(answers, expected):
    assert calculate_score(*answers) == expected


@pytest.mark.parametrize("bad", [-1, 11, 7.0, "7", None, True])
def test_each_answer_position_rejects_invalid_values(bad):
    for position in range(3):
        answers = [5, 5, 5]
        answers[position] = bad
        with pytest.raises(InvalidAnswerError):
            calculate_score(*answers)
