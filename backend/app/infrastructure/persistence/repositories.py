"""PostgreSQL repository. Every read is tenant-scoped; the caller owns the transaction."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.errors import UniqueViolation

from app.application.errors import ConcurrentDraftError
from app.domain.check_ins.check_in import CheckIn, CheckInStatus
from app.domain.exceptions.errors import CheckInAlreadySubmittedError
from app.domain.users import Role, User
from app.domain.wellbeing.aggregation import SubmittedRecord
from app.infrastructure.persistence.connection import DictConnection

_CHECK_IN_COLUMNS = (
    "id, employee_id, organization_id, team_id, connectedness, support, workload,"
    " score, status, created_at, updated_at, submitted_at"
)

_UPSERT_CHECK_IN = f"""
insert into check_ins ({_CHECK_IN_COLUMNS})
values (%(id)s, %(employee_id)s, %(organization_id)s, %(team_id)s, %(connectedness)s,
        %(support)s, %(workload)s, %(score)s, %(status)s, %(created_at)s, %(updated_at)s,
        %(submitted_at)s)
on conflict (id) do update set
  connectedness = excluded.connectedness,
  support = excluded.support,
  workload = excluded.workload,
  score = excluded.score,
  status = excluded.status,
  updated_at = excluded.updated_at,
  submitted_at = excluded.submitted_at
where check_ins.status = 'DRAFT'
"""


def _to_user(row: dict[str, Any]) -> User:
    return User(
        id=row["id"],
        organization_id=row["organization_id"],
        team_id=row["team_id"],
        email=row["email"],
        password_hash=row["password_hash"],
        role=Role(row["role"]),
    )


def _to_check_in(row: dict[str, Any]) -> CheckIn:
    return CheckIn(
        id=row["id"],
        employee_id=row["employee_id"],
        organization_id=row["organization_id"],
        team_id=row["team_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        status=CheckInStatus(row["status"]),
        connectedness=row["connectedness"],
        support=row["support"],
        workload=row["workload"],
        score=row["score"],
        submitted_at=row["submitted_at"],
    )


def _lock(for_update: bool) -> str:
    return " for update" if for_update else ""


class PostgresRepository:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    # --- users ---------------------------------------------------------------------------
    def get_user_by_email(self, email: str) -> User | None:
        row = self._conn.execute(
            "select id, organization_id, team_id, email, password_hash, role"
            " from users where lower(email) = lower(%s)",
            (email,),
        ).fetchone()
        return _to_user(row) if row else None

    def get_user(self, user_id: UUID) -> User | None:
        row = self._conn.execute(
            "select id, organization_id, team_id, email, password_hash, role"
            " from users where id = %s",
            (user_id,),
        ).fetchone()
        return _to_user(row) if row else None

    # --- check-ins (always scoped to the owning employee) --------------------------------
    def find_draft(self, employee_id: UUID, *, for_update: bool = False) -> CheckIn | None:
        row = self._conn.execute(
            f"select {_CHECK_IN_COLUMNS} from check_ins"
            " where employee_id = %s and status = 'DRAFT'" + _lock(for_update),
            (employee_id,),
        ).fetchone()
        return _to_check_in(row) if row else None

    def find_by_id_for_employee(
        self, check_in_id: UUID, employee_id: UUID, *, for_update: bool = False
    ) -> CheckIn | None:
        row = self._conn.execute(
            f"select {_CHECK_IN_COLUMNS} from check_ins where id = %s and employee_id = %s"
            + _lock(for_update),
            (check_in_id, employee_id),
        ).fetchone()
        return _to_check_in(row) if row else None

    def find_latest_submitted(self, employee_id: UUID) -> CheckIn | None:
        row = self._conn.execute(
            f"select {_CHECK_IN_COLUMNS} from check_ins"
            " where employee_id = %s and status = 'SUBMITTED'"
            " order by submitted_at desc limit 1",
            (employee_id,),
        ).fetchone()
        return _to_check_in(row) if row else None

    def save(self, check_in: CheckIn) -> None:
        """Persist a draft. A racing first save surfaces as ConcurrentDraftError."""
        try:
            self._save(check_in)
        except UniqueViolation as exc:
            raise ConcurrentDraftError("a draft already exists for this employee") from exc

    def _save(self, check_in: CheckIn) -> None:
        """Insert or update a DRAFT row. A row that is already SUBMITTED is never touched."""
        cur = self._conn.execute(
            _UPSERT_CHECK_IN,
            {
                "id": check_in.id,
                "employee_id": check_in.employee_id,
                "organization_id": check_in.organization_id,
                "team_id": check_in.team_id,
                "connectedness": check_in.connectedness,
                "support": check_in.support,
                "workload": check_in.workload,
                "score": check_in.score,
                "status": check_in.status.value,
                "created_at": check_in.created_at,
                "updated_at": check_in.updated_at,
                "submitted_at": check_in.submitted_at,
            },
        )
        if cur.rowcount == 0:
            raise CheckInAlreadySubmittedError("check-in was already submitted")

    # --- aggregate inputs (organization-scoped in SQL; never returns answers) ------------
    def submitted_records(self, organization_id: UUID, team_id: UUID | None) -> list[SubmittedRecord]:
        rows = self._conn.execute(
            "select employee_id, submitted_at, score from check_ins"
            " where organization_id = %s and status = 'SUBMITTED'"
            " and (%s::uuid is null or team_id = %s)",
            (organization_id, team_id, team_id),
        ).fetchall()
        return [SubmittedRecord(r["employee_id"], r["submitted_at"], r["score"]) for r in rows]

    def eligible_count(self, organization_id: UUID, team_id: UUID | None) -> int:
        row = self._conn.execute(
            "select count(*) as n from users"
            " where organization_id = %s and role = 'EMPLOYEE'"
            " and (%s::uuid is null or team_id = %s)",
            (organization_id, team_id, team_id),
        ).fetchone()
        assert row is not None  # count(*) always yields a row
        return int(row["n"])

    def team_in_organization(self, team_id: UUID, organization_id: UUID) -> bool:
        row = self._conn.execute(
            "select 1 as ok from teams where id = %s and organization_id = %s",
            (team_id, organization_id),
        ).fetchone()
        return row is not None

    def commit(self) -> None:
        self._conn.commit()

    def list_teams(self, organization_id: UUID) -> list[tuple[UUID, str]]:
        rows = self._conn.execute(
            "select id, name from teams where organization_id = %s order by name",
            (organization_id,),
        ).fetchall()
        return [(r["id"], r["name"]) for r in rows]

    def rollback(self) -> None:
        self._conn.rollback()
