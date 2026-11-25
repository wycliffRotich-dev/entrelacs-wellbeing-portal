"""Wellbeing score: ((connectedness + support + workload) / 3) * 10, rounded half-up to 1 dp."""
from decimal import ROUND_HALF_UP, Decimal

from app.domain.check_ins.answers import validate_answer

_ONE_DECIMAL = Decimal("0.1")


def calculate_score(connectedness: object, support: object, workload: object) -> Decimal:
    total = sum(validate_answer(a) for a in (connectedness, support, workload))
    return (Decimal(total) * 10 / 3).quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)
