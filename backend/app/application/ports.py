"""What the application layer needs from infrastructure. Implemented by the Postgres adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.check_ins.check_in import CheckIn
from app.domain.users import User
from app.domain.wellbeing.aggregation import SubmittedRecord


class Repository(Protocol):
    def get_user_by_email(self, email: str) -> User | None: ...

    def get_user(self, user_id: UUID) -> User | None: ...

    def find_draft(self, employee_id: UUID, *, for_update: bool = False) -> CheckIn | None: ...

    def find_by_id_for_employee(
        self, check_in_id: UUID, employee_id: UUID, *, for_update: bool = False
    ) -> CheckIn | None: ...

    def find_latest_submitted(self, employee_id: UUID) -> CheckIn | None: ...

    def save(self, check_in: CheckIn) -> None: ...

    def submitted_records(
        self, organization_id: UUID, team_id: UUID | None
    ) -> list[SubmittedRecord]: ...

    def eligible_count(self, organization_id: UUID, team_id: UUID | None) -> int: ...

    def team_in_organization(self, team_id: UUID, organization_id: UUID) -> bool: ...

    def list_teams(self, organization_id: UUID) -> list[tuple[UUID, str]]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: UUID, *, now: datetime) -> str: ...
