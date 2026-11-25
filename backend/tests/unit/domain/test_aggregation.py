from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.exceptions.errors import NaiveDatetimeError
from app.domain.wellbeing.aggregation import MIN_RESPONDENTS, SubmittedRecord, summarize

UTC = timezone.utc
OCT = datetime(2026, 10, 1, tzinfo=UTC)
MID = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def rec(score, at=MID, employee=None):
    return SubmittedRecord(employee_id=employee or uuid4(), submitted_at=at, score=Decimal(score))


def group(*scores):
    return [rec(s) for s in scores]


def test_threshold_is_five():
    assert MIN_RESPONDENTS == 5


def test_window_is_half_open_in_utc():
    inside_start = rec("10.0", at=datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC))
    inside_end = rec("20.0", at=datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC))
    too_late = rec("90.0", at=datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC))
    too_early = rec("90.0", at=datetime(2026, 9, 30, 23, 59, 59, tzinfo=UTC))
    s = summarize([inside_start, inside_end, too_late, too_early], 10, OCT)
    assert s.respondent_count == 2


def test_december_window_ends_at_january_first():
    dec = datetime(2026, 12, 1, tzinfo=UTC)
    last = rec("10.0", at=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC))
    jan = rec("10.0", at=datetime(2027, 1, 1, tzinfo=UTC))
    assert summarize([last, jan], 5, dec).respondent_count == 1


def test_employee_counts_once_with_latest_submission():
    e = uuid4()
    older = rec("10.0", at=datetime(2026, 10, 2, tzinfo=UTC), employee=e)
    newer = rec("80.0", at=datetime(2026, 10, 20, tzinfo=UTC), employee=e)
    s = summarize([newer, older, *group("80.0", "80.0", "80.0", "80.0")], 10, OCT)
    assert s.respondent_count == 5
    assert s.average_score == Decimal("80.0")


def test_latest_submission_wins_even_when_its_score_is_lower():
    e = uuid4()
    older = rec("90.0", at=datetime(2026, 10, 2, tzinfo=UTC), employee=e)
    newer = rec("30.0", at=datetime(2026, 10, 20, tzinfo=UTC), employee=e)
    s = summarize([older, newer, *group("30.0", "30.0", "30.0", "30.0")], 10, OCT)
    assert s.average_score == Decimal("30.0")


def test_out_of_window_later_submission_does_not_replace_in_window_one():
    e = uuid4()
    in_month = rec("60.0", at=datetime(2026, 10, 30, tzinfo=UTC), employee=e)
    next_month = rec("10.0", at=datetime(2026, 11, 2, tzinfo=UTC), employee=e)
    s = summarize([in_month, next_month, *group("60.0", "60.0", "60.0", "60.0")], 10, OCT)
    assert s.average_score == Decimal("60.0")


@pytest.mark.parametrize("n", [0, 1, 4])
def test_fewer_than_five_respondents_withholds_average(n):
    s = summarize(group(*["70.0"] * n), 10, OCT)
    assert s.suppressed is True
    assert s.average_score is None
    assert s.respondent_count == n


def test_exactly_five_respondents_reveals_average():
    s = summarize(group("10.0", "20.0", "30.0", "40.0", "50.0"), 10, OCT)
    assert s.suppressed is False
    assert s.average_score == Decimal("30.0")


def test_average_rounds_half_up_on_a_real_tie():
    # 5 x 50.0 + 50.3 = 300.3 over 6 respondents = exactly 50.05
    s = summarize(group("50.0", "50.0", "50.0", "50.0", "50.0", "50.3"), 10, OCT)
    assert s.average_score == Decimal("50.1")


def test_participation_rounds_half_up_on_a_real_tie():
    # 1 / 16 * 100 = exactly 6.25
    s = summarize(group("70.0"), 16, OCT)
    assert s.participation_rate == Decimal("6.3")


def test_participation_and_counts_are_returned_when_suppressed():
    s = summarize(group("70.0", "70.0"), 8, OCT)
    assert s.suppressed is True
    assert (s.respondent_count, s.eligible_count) == (2, 8)
    assert s.participation_rate == Decimal("25.0")


def test_zero_eligible_employees_has_no_participation_rate():
    s = summarize([], 0, OCT)
    assert s.participation_rate is None
    assert s.eligible_count == 0


def test_naive_submission_time_is_rejected():
    naive = SubmittedRecord(uuid4(), datetime(2026, 10, 5), Decimal("50.0"))
    with pytest.raises(NaiveDatetimeError):
        summarize([naive], 5, OCT)


def test_naive_month_start_is_rejected():
    with pytest.raises(NaiveDatetimeError):
        summarize([], 5, datetime(2026, 10, 1))


def test_summary_has_no_field_that_can_carry_individual_data():
    names = {f.name for f in fields(summarize([], 1, OCT))}
    assert names == {
        "respondent_count",
        "eligible_count",
        "participation_rate",
        "average_score",
        "suppressed",
    }
