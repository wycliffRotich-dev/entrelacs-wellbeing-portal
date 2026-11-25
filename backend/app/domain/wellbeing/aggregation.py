"""Monthly wellbeing aggregation with minimum-respondent suppression. Pure: no DB, no clock."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.domain.exceptions.errors import NaiveDatetimeError

MIN_RESPONDENTS = 5
_ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class SubmittedRecord:
    employee_id: UUID
    submitted_at: datetime
    score: Decimal


@dataclass(frozen=True, slots=True)
class WellbeingSummary:
    respondent_count: int
    eligible_count: int
    participation_rate: Decimal | None
    average_score: Decimal | None
    suppressed: bool


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDatetimeError("datetime must be timezone-aware")
    return value


def _next_month(start: datetime) -> datetime:
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def _round_one_decimal(value: Decimal) -> Decimal:
    return value.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


def summarize(
    submissions: Iterable[SubmittedRecord], eligible_count: int, month_start: datetime
) -> WellbeingSummary:
    start = _require_aware(month_start)
    end = _next_month(start)
    records = list(submissions)
    for r in records:
        _require_aware(r.submitted_at)

    # Filter to the window first, so an out-of-window submission can never displace an in-window one.
    latest: dict[UUID, SubmittedRecord] = {}
    for r in records:
        if not start <= r.submitted_at < end:
            continue
        current = latest.get(r.employee_id)
        if current is None or r.submitted_at > current.submitted_at:
            latest[r.employee_id] = r

    respondents = len(latest)
    participation = (
        _round_one_decimal(Decimal(respondents) * 100 / Decimal(eligible_count))
        if eligible_count > 0
        else None
    )
    suppressed = respondents < MIN_RESPONDENTS
    average = (
        None
        if suppressed
        else _round_one_decimal(sum(r.score for r in latest.values()) / Decimal(respondents))
    )
    return WellbeingSummary(
        respondent_count=respondents,
        eligible_count=eligible_count,
        participation_rate=participation,
        average_score=average,
        suppressed=suppressed,
    )
