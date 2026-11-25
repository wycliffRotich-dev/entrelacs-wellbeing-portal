from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)


def insert_org(cur):
    org_id = uuid4()
    cur.execute("insert into organizations (id, name) values (%s, %s)", (org_id, f"org-{org_id}"))
    return org_id


def insert_team(cur, org_id):
    team_id = uuid4()
    cur.execute(
        "insert into teams (id, organization_id, name) values (%s, %s, %s)",
        (team_id, org_id, f"team-{team_id}"),
    )
    return team_id


def insert_user(cur, org_id, team_id, role="EMPLOYEE", email=None):
    user_id = uuid4()
    cur.execute(
        "insert into users (id, organization_id, team_id, email, password_hash, role)"
        " values (%s, %s, %s, %s, 'x', %s)",
        (user_id, org_id, team_id, email or f"{user_id}@example.test", role),
    )
    return user_id


def insert_check_in(cur, employee_id, org_id, team_id, submitted=False):
    check_in_id = uuid4()
    if submitted:
        cur.execute(
            "insert into check_ins (id, employee_id, organization_id, team_id, connectedness,"
            " support, workload, score, status, created_at, updated_at, submitted_at)"
            " values (%s, %s, %s, %s, 5, 5, 5, 50.0, 'SUBMITTED', %s, %s, %s)",
            (check_in_id, employee_id, org_id, team_id, NOW, NOW, NOW),
        )
    else:
        cur.execute(
            "insert into check_ins (id, employee_id, organization_id, team_id, status,"
            " created_at, updated_at) values (%s, %s, %s, %s, 'DRAFT', %s, %s)",
            (check_in_id, employee_id, org_id, team_id, NOW, NOW),
        )
    return check_in_id


@pytest.fixture
def world(db):
    cur = db.cursor()
    org_a, org_b = insert_org(cur), insert_org(cur)
    team_a, team_b = insert_team(cur, org_a), insert_team(cur, org_b)
    employee_a = insert_user(cur, org_a, team_a)
    return {"cur": cur, "org_a": org_a, "org_b": org_b, "team_a": team_a,
            "team_b": team_b, "employee_a": employee_a}


def test_check_in_cannot_claim_another_organization(world):
    w = world
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert_check_in(w["cur"], w["employee_a"], w["org_b"], w["team_b"])


def test_check_in_cannot_use_another_organizations_team(world):
    w = world
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_b"])


def test_second_draft_for_same_employee_is_rejected(world):
    w = world
    insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"])
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"])


def test_submitted_check_in_cannot_be_updated(world):
    w = world
    cid = insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"], submitted=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        w["cur"].execute("update check_ins set connectedness = 1 where id = %s", (cid,))


def test_submitted_check_in_cannot_be_deleted(world):
    w = world
    cid = insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"], submitted=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        w["cur"].execute("delete from check_ins where id = %s", (cid,))


def test_draft_can_transition_to_submitted(world):
    w = world
    cid = insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"])
    w["cur"].execute(
        "update check_ins set connectedness = 5, support = 5, workload = 5, score = 50.0,"
        " status = 'SUBMITTED', submitted_at = %s where id = %s",
        (NOW, cid),
    )
    w["cur"].execute("select status from check_ins where id = %s", (cid,))
    assert w["cur"].fetchone()[0] == "SUBMITTED"


def test_new_draft_is_allowed_after_a_submission(world):
    w = world
    insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"], submitted=True)
    insert_check_in(w["cur"], w["employee_a"], w["org_a"], w["team_a"])


def test_submitted_row_requires_all_answers(world):
    w = world
    with pytest.raises(psycopg.errors.CheckViolation):
        w["cur"].execute(
            "insert into check_ins (id, employee_id, organization_id, team_id, connectedness,"
            " score, status, created_at, updated_at, submitted_at)"
            " values (%s, %s, %s, %s, 5, 50.0, 'SUBMITTED', %s, %s, %s)",
            (uuid4(), w["employee_a"], w["org_a"], w["team_a"], NOW, NOW, NOW),
        )


def test_employee_requires_a_team(world):
    w = world
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_user(w["cur"], w["org_a"], None, role="EMPLOYEE")


def test_hr_user_must_not_have_a_team(world):
    w = world
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_user(w["cur"], w["org_a"], w["team_a"], role="HR")


def test_email_is_unique_case_insensitively(world):
    w = world
    insert_user(w["cur"], w["org_a"], w["team_a"], email="Same@Example.test")
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_user(w["cur"], w["org_a"], w["team_a"], email="same@example.TEST")
