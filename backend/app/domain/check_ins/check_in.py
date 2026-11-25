"""CheckIn aggregate: draft -> submitted lifecycle. No framework or persistence imports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.check_ins.answers import validate_answer
from app.domain.check_ins.score import calculate_score
from app.domain.exceptions.errors import CheckInAlreadySubmittedError, IncompleteCheckInError


class CheckInStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"


@dataclass
class CheckIn:
    id: UUID
    employee_id: UUID
    organization_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
    status: CheckInStatus = CheckInStatus.DRAFT
    connectedness: int | None = None
    support: int | None = None
    workload: int | None = None
    score: Decimal | None = None
    submitted_at: datetime | None = None

    @classmethod
    def start(
        cls, *, employee_id: UUID, organization_id: UUID, team_id: UUID | None, now: datetime
    ) -> CheckIn:
        return cls(
            id=uuid4(),
            employee_id=employee_id,
            organization_id=organization_id,
            team_id=team_id,
            created_at=now,
            updated_at=now,
        )

    def save_draft(
        self,
        *,
        now: datetime,
        connectedness: object = None,
        support: object = None,
        workload: object = None,
    ) -> None:
        """Update provided answers only (None = not provided). All-or-nothing."""
        self._ensure_draft()
        provided = {
            name: validate_answer(value)
            for name, value in (
                ("connectedness", connectedness),
                ("support", support),
                ("workload", workload),
            )
            if value is not None
        }
        for name, value in provided.items():
            setattr(self, name, value)
        self.updated_at = now

    def submit(self, *, now: datetime) -> None:
        self._ensure_draft()
        if None in (self.connectedness, self.support, self.workload):
            raise IncompleteCheckInError("all three answers are required to submit")
        self.score = calculate_score(self.connectedness, self.support, self.workload)
        self.status = CheckInStatus.SUBMITTED
        self.submitted_at = now
        self.updated_at = now

    def _ensure_draft(self) -> None:
        if self.status is CheckInStatus.SUBMITTED:
            raise CheckInAlreadySubmittedError("a submitted check-in cannot be changed")
