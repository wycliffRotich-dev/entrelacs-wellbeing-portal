from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from app.domain.check_ins.check_in import CheckIn, CheckInStatus
from app.domain.exceptions.errors import CheckInAlreadySubmittedError
from app.infrastructure.persistence.repositories import PostgresRepository

ROOT = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    password = (ROOT / "secrets" / "postgres_password").read_text(encoding="utf-8").strip()
    c = psycopg.connect(
        host="127.0.0.1", port=5433, dbname="wellbeing_test", user="wellbeing",
        password=password, row_factory=dict_row,
    )
    try:
        yield c
    finally:
        c.rollback()
        c.close()


@pytest.fixture
def repo(conn):
    return PostgresRepository(conn)


def seed(conn):
    cur = conn.cursor()
    org, other_org = uuid4(), uuid4()
    for o in (org, other_org):
        cur.execute("insert into organizations (id, name) values (%s, %s)", (o, f"org-{o}"))
    team, team2, other_team = uuid4(), uuid4(), uuid4()
    for t, o in ((team, org), (team2, org), (other_team, other_org)):
        cur.execute("insert into teams (id, organization_id, name) values (%s, %s, %s)", (t, o, f"t-{t}"))
    users = {}
    for key, o, t, role in (
        ("emp1", org, team, "EMPLOYEE"), ("emp2", org, team, "EMPLOYEE"),
        ("emp3", org, team2, "EMPLOYEE"), ("other", other_org, other_team, "EMPLOYEE"),
        ("hr", org, None, "HR"),
    ):
        uid = uuid4()
        users[key] = uid
        cur.execute(
            "insert into users (id, organization_id, team_id, email, password_hash, role)"
            " values (%s, %s, %s, %s, 'x', %s)", (uid, o, t, f"{uid}@Example.test", role))
    return {"org": org, "other_org": other_org, "team": team, "team2": team2,
            "other_team": other_team, **users}


def full_check_in(w, employee, team, org=None, at=T0):
    c = CheckIn.start(employee_id=w[employee], organization_id=org or w["org"], team_id=team, now=at)
    c.save_draft(connectedness=10, support=10, workload=9, now=at)
    return c


def test_user_lookup_by_email_is_case_insensitive_and_has_role_and_tenant(conn, repo):
    w = seed(conn)
    u = repo.get_user_by_email(f"{w['emp1']}@EXAMPLE.TEST")
    assert u.id == w["emp1"] and u.role == "EMPLOYEE"
    assert u.organization_id == w["org"] and u.team_id == w["team"]


def test_unknown_user_returns_none(repo):
    assert repo.get_user(uuid4()) is None
    assert repo.get_user_by_email("nobody@example.test") is None


def test_draft_round_trip_preserves_partial_answers(conn, repo):
    w = seed(conn)
    c = CheckIn.start(employee_id=w["emp1"], organization_id=w["org"], team_id=w["team"], now=T0)
    c.save_draft(connectedness=7, now=T0)
    repo.save(c)
    found = repo.find_draft(w["emp1"])
    assert found.id == c.id and found.connectedness == 7 and found.support is None


def test_saving_a_draft_again_updates_the_same_row(conn, repo):
    w = seed(conn)
    c = CheckIn.start(employee_id=w["emp1"], organization_id=w["org"], team_id=w["team"], now=T0)
    c.save_draft(connectedness=7, now=T0)
    repo.save(c)
    c.save_draft(support=3, now=T1)
    repo.save(c)
    found = repo.find_draft(w["emp1"])
    assert (found.connectedness, found.support) == (7, 3)


def test_find_by_id_for_employee_hides_other_employees_check_ins(conn, repo):
    w = seed(conn)
    c = full_check_in(w, "emp1", w["team"])
    repo.save(c)
    assert repo.find_by_id_for_employee(c.id, w["emp1"]).id == c.id
    assert repo.find_by_id_for_employee(c.id, w["emp2"]) is None


def test_submit_persists_score_and_status(conn, repo):
    w = seed(conn)
    c = full_check_in(w, "emp1", w["team"])
    repo.save(c)
    c.submit(now=T1)
    repo.save(c)
    found = repo.find_by_id_for_employee(c.id, w["emp1"])
    assert found.status is CheckInStatus.SUBMITTED
    assert found.score == Decimal("96.7") and found.submitted_at == T1


def test_second_submit_of_same_check_in_is_rejected_atomically(conn, repo):
    w = seed(conn)
    first = full_check_in(w, "emp1", w["team"])
    repo.save(first)
    stale = repo.find_draft(w["emp1"])  # a concurrent request holding the same draft
    first.submit(now=T1)
    repo.save(first)
    stale.submit(now=T1)
    with pytest.raises(CheckInAlreadySubmittedError):
        repo.save(stale)


def test_submitted_records_are_scoped_to_org_and_exclude_drafts(conn, repo):
    w = seed(conn)
    for emp, team in (("emp1", w["team"]), ("emp3", w["team2"])):
        c = full_check_in(w, emp, team)
        repo.save(c)
        c.submit(now=T1)
        repo.save(c)
    draft = full_check_in(w, "emp2", w["team"])
    repo.save(draft)
    other = full_check_in(w, "other", w["other_team"], org=w["other_org"])
    repo.save(other)
    other.submit(now=T1)
    repo.save(other)
    org_records = repo.submitted_records(w["org"], None)
    assert {r.employee_id for r in org_records} == {w["emp1"], w["emp3"]}
    team_records = repo.submitted_records(w["org"], w["team"])
    assert {r.employee_id for r in team_records} == {w["emp1"]}


def test_eligible_count_counts_only_employees_in_scope(conn, repo):
    w = seed(conn)
    assert repo.eligible_count(w["org"], None) == 3  # hr and other-org users excluded
    assert repo.eligible_count(w["org"], w["team"]) == 2
    assert repo.eligible_count(w["org"], w["team2"]) == 1
    assert repo.eligible_count(w["other_org"], w["team"]) == 0  # team from another org


def test_team_belongs_to_organization_lookup(conn, repo):
    w = seed(conn)
    assert repo.team_in_organization(w["team"], w["org"]) is True
    assert repo.team_in_organization(w["other_team"], w["org"]) is False
    assert repo.team_in_organization(uuid4(), w["org"]) is False
