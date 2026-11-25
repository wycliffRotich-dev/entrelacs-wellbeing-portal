"""HTTP request and response shapes. Ownership and score are never client-supplied."""
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.check_ins.check_in import CheckIn
from app.domain.users import User
from app.domain.wellbeing.aggregation import WellbeingSummary

Answer = Annotated[int, Field(strict=True, ge=0, le=10)]


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_StrictRequest):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class DraftRequest(_StrictRequest):
    connectedness: Answer | None = None
    support: Answer | None = None
    workload: Answer | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class MeResponse(BaseModel):
    id: UUID
    email: str
    role: str
    organization_id: UUID
    team_id: UUID | None

    @classmethod
    def from_domain(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=user.email,
            role=user.role.value,
            organization_id=user.organization_id,
            team_id=user.team_id,
        )


class CheckInResponse(BaseModel):
    id: UUID
    status: str
    connectedness: int | None
    support: int | None
    workload: int | None
    score: float | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None

    @classmethod
    def from_domain(cls, c: CheckIn) -> Self:
        return cls(
            id=c.id,
            status=c.status.value,
            connectedness=c.connectedness,
            support=c.support,
            workload=c.workload,
            score=float(c.score) if c.score is not None else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
            submitted_at=c.submitted_at,
        )


class CurrentCheckInsResponse(BaseModel):
    draft: CheckInResponse | None
    latest_submitted: CheckInResponse | None


class TeamResponse(BaseModel):
    id: UUID
    name: str


class WellbeingResponse(BaseModel):
    """Aggregate only. No individual answers, scores or identifiers can be expressed here."""

    reporting_month: str
    team_id: UUID | None
    respondent_count: int
    eligible_count: int
    participation_rate: float | None
    average_score: float | None
    suppressed: bool

    @classmethod
    def from_domain(cls, s: WellbeingSummary, month_start: datetime, team_id: UUID | None) -> Self:
        return cls(
            reporting_month=month_start.strftime("%Y-%m"),
            team_id=team_id,
            respondent_count=s.respondent_count,
            eligible_count=s.eligible_count,
            participation_rate=(
                float(s.participation_rate) if s.participation_rate is not None else None
            ),
            average_score=float(s.average_score) if s.average_score is not None else None,
            suppressed=s.suppressed,
        )
