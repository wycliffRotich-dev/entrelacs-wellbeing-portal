"""Synthetic demo data. Fictional organizations and people only. Credentials are local-only."""
from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.config import load_settings
from app.domain.check_ins.score import calculate_score
from app.infrastructure.persistence.connection import DictConnection, connect
from app.infrastructure.security.passwords import hash_password

DEMO_PASSWORD = "demo-password-123"  # local-only demonstration credential, not a real secret
HR_EMAILS = {
    "Northwind Health": "hr@northwind.example.test",
    "Contoso Labs": "hr@contoso.example.test",
}

Answers = tuple[int | None, int | None, int | None]


@dataclass(frozen=True)
class Submission:
    month: int
    day: int
    answers: tuple[int, int, int]


@dataclass(frozen=True)
class Employee:
    name: str
    submissions: tuple[Submission, ...] = ()
    draft: Answers | None = None


@dataclass(frozen=True)
class Team:
    name: str
    employees: tuple[Employee, ...] = ()


@dataclass(frozen=True)
class Org:
    name: str
    domain: str
    teams: tuple[Team, ...]


def sub(day: int, answers: tuple[int, int, int], month: int = 10) -> Submission:
    return Submission(month=month, day=day, answers=answers)


DATA: tuple[Org, ...] = (
    Org(
        "Northwind Health",
        "northwind.example.test",
        (
            Team(  # exactly 5 respondents: the boundary where the average is revealed
                "Platform",
                (
                    Employee("maya", (sub(6, (7, 8, 6)), sub(20, (9, 8, 8)))),  # repeat check-in
                    Employee("noah", (sub(8, (6, 6, 7)),)),
                    Employee("priya", (sub(12, (8, 7, 9)),)),
                    Employee("liam", (sub(14, (5, 6, 4)), sub(28, (3, 3, 3), month=9))),
                    Employee("zoe", (sub(3, (9, 9, 8)),)),
                    Employee("omar", draft=(7, None, None)),  # draft only: not a respondent
                    Employee("hana"),
                ),
            ),
            Team(  # 3 respondents: average withheld
                "Support",
                (
                    Employee("ivan", (sub(5, (4, 5, 3)),)),
                    Employee("lena", (sub(9, (6, 6, 6)), sub(22, (7, 6, 5)))),
                    Employee("tariq", (sub(15, (8, 8, 9)),)),
                    Employee("sara", draft=(3, 4, None)),
                ),
            ),
            Team(  # no respondents in the reporting month
                "Design",
                (
                    Employee("kofi", draft=(5, None, None)),
                    Employee("mei"),
                    Employee("paul", (sub(2, (6, 6, 6), month=11),)),  # outside the month
                ),
            ),
            Team("Ops"),  # no eligible employees
        ),
    ),
    Org(
        "Contoso Labs",
        "contoso.example.test",
        (
            Team(
                "Engineering",
                (
                    Employee("amir", (sub(4, (8, 8, 7)),)),
                    Employee("bea", (sub(7, (6, 7, 6)),)),
                    Employee("chen", (sub(9, (7, 7, 8)), sub(21, (5, 6, 5)))),
                    Employee("dara", (sub(11, (9, 8, 9)),)),
                    Employee("eli", (sub(13, (4, 5, 4)),)),
                    Employee("fay", (sub(18, (7, 6, 7)),)),
                ),
            ),
            Team(
                "Sales",
                (
                    Employee("gus", (sub(6, (5, 4, 3)),)),
                    Employee("hugo", (sub(10, (6, 6, 5)),)),
                    Employee("ines", draft=(2, None, None)),
                ),
            ),
        ),
    ),
)


def _at(month: int, day: int, hour: int = 10) -> datetime:
    return datetime(2026, month, day, hour, 0, tzinfo=UTC)


def _insert_user(
    conn: DictConnection,
    org_id: UUID,
    team_id: UUID | None,
    email: str,
    password_hash: str,
    role: str,
) -> UUID:
    user_id = uuid4()
    conn.execute(
        "insert into users (id, organization_id, team_id, email, password_hash, role)"
        " values (%s, %s, %s, %s, %s, %s)",
        (user_id, org_id, team_id, email, password_hash, role),
    )
    return user_id


def _insert_submitted(
    conn: DictConnection, employee_id: UUID, org_id: UUID, team_id: UUID, s: Submission
) -> None:
    c, sup, w = s.answers
    at = _at(s.month, s.day)
    conn.execute(
        "insert into check_ins (id, employee_id, organization_id, team_id, connectedness,"
        " support, workload, score, status, created_at, updated_at, submitted_at)"
        " values (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s, %s, %s)",
        (uuid4(), employee_id, org_id, team_id, c, sup, w, calculate_score(c, sup, w), at, at, at),
    )


def _insert_draft(
    conn: DictConnection, employee_id: UUID, org_id: UUID, team_id: UUID, answers: Answers
) -> None:
    c, sup, w = answers
    at = _at(10, 16)
    conn.execute(
        "insert into check_ins (id, employee_id, organization_id, team_id, connectedness,"
        " support, workload, status, created_at, updated_at)"
        " values (%s, %s, %s, %s, %s, %s, %s, 'DRAFT', %s, %s)",
        (uuid4(), employee_id, org_id, team_id, c, sup, w, at, at),
    )


def seed(conn: DictConnection, *, reset: bool) -> bool:
    """Insert the demo data. Returns False, changing nothing, if data exists and not reset."""
    existing = conn.execute("select count(*) as n from organizations").fetchone()
    assert existing is not None  # count(*) always yields a row
    if existing["n"] and not reset:
        return False
    if reset:
        conn.execute("truncate check_ins, users, teams, organizations cascade")
    password_hash = hash_password(DEMO_PASSWORD)
    for org in DATA:
        org_id = uuid4()
        conn.execute("insert into organizations (id, name) values (%s, %s)", (org_id, org.name))
        _insert_user(conn, org_id, None, HR_EMAILS[org.name], password_hash, "HR")
        for team in org.teams:
            team_id = uuid4()
            conn.execute(
                "insert into teams (id, organization_id, name) values (%s, %s, %s)",
                (team_id, org_id, team.name),
            )
            for emp in team.employees:
                email = f"{emp.name}@{org.domain}"
                emp_id = _insert_user(conn, org_id, team_id, email, password_hash, "EMPLOYEE")
                for s in emp.submissions:
                    _insert_submitted(conn, emp_id, org_id, team_id, s)
                if emp.draft is not None:
                    _insert_draft(conn, emp_id, org_id, team_id, emp.draft)
    return True


def main(argv: Sequence[str]) -> int:
    settings = load_settings(os.environ)
    with connect(settings) as conn:
        seeded = seed(conn, reset="--reset" in argv)
    if not seeded:
        print("Database already has data. Re-run with --reset to replace it.")
        return 0
    print(f"Seeded. Local-only demo password for every account: {DEMO_PASSWORD}")
    for org in DATA:
        print(f"{org.name}: HR {HR_EMAILS[org.name]}")
        for team in org.teams:
            names = ", ".join(f"{e.name}@{org.domain}" for e in team.employees) or "(no employees)"
            print(f"  {team.name}: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
