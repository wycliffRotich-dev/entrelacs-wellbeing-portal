from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.check_ins.check_in import CheckIn, CheckInStatus
from app.domain.exceptions.errors import (
    CheckInAlreadySubmittedError,
    IncompleteCheckInError,
    InvalidAnswerError,
)

T0 = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)
T2 = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def new_draft():
    return CheckIn.start(employee_id=uuid4(), organization_id=uuid4(), team_id=uuid4(), now=T0)


def test_new_check_in_is_an_empty_draft():
    c = new_draft()
    assert c.status is CheckInStatus.DRAFT
    assert (c.connectedness, c.support, c.workload) == (None, None, None)
    assert c.score is None and c.submitted_at is None
    assert c.created_at == T0 and c.updated_at == T0


def test_draft_accepts_partial_answers_and_updates_timestamp():
    c = new_draft()
    c.save_draft(connectedness=7, now=T1)
    assert c.connectedness == 7 and c.support is None
    assert c.updated_at == T1 and c.score is None


def test_draft_save_overwrites_only_provided_answers():
    c = new_draft()
    c.save_draft(connectedness=7, support=4, now=T1)
    c.save_draft(support=9, now=T2)
    assert (c.connectedness, c.support, c.workload) == (7, 9, None)


def test_draft_rejects_invalid_answer_and_keeps_previous_state():
    c = new_draft()
    c.save_draft(connectedness=7, now=T1)
    with pytest.raises(InvalidAnswerError):
        c.save_draft(connectedness=11, support=5, now=T2)
    assert (c.connectedness, c.support) == (7, None)
    assert c.updated_at == T1


@pytest.mark.parametrize("missing", ["connectedness", "support", "workload"])
def test_submit_requires_all_three_answers(missing):
    answers = {"connectedness": 5, "support": 5, "workload": 5}
    del answers[missing]
    c = new_draft()
    c.save_draft(now=T1, **answers)
    with pytest.raises(IncompleteCheckInError):
        c.submit(now=T2)
    assert c.status is CheckInStatus.DRAFT


def test_submit_computes_score_and_locks_check_in():
    c = new_draft()
    c.save_draft(connectedness=10, support=10, workload=9, now=T1)
    c.submit(now=T2)
    assert c.status is CheckInStatus.SUBMITTED
    assert c.score == Decimal("96.7")
    assert c.submitted_at == T2 and c.updated_at == T2


def test_submitted_check_in_rejects_edits():
    c = new_draft()
    c.save_draft(connectedness=5, support=5, workload=5, now=T1)
    c.submit(now=T2)
    with pytest.raises(CheckInAlreadySubmittedError):
        c.save_draft(connectedness=9, now=T2)
    assert c.connectedness == 5


def test_submitted_check_in_rejects_second_submit():
    c = new_draft()
    c.save_draft(connectedness=5, support=5, workload=5, now=T1)
    c.submit(now=T2)
    with pytest.raises(CheckInAlreadySubmittedError):
        c.submit(now=T2)
