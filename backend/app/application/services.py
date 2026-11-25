"""Application services: orchestrate domain objects and own the transaction boundary."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.errors import ConcurrentDraftError, InvalidCredentialsError, NotFoundError
from app.application.ports import Repository, TokenIssuer
from app.domain.check_ins.check_in import CheckIn
from app.domain.users import User
from app.domain.wellbeing.aggregation import WellbeingSummary, summarize

Clock = Callable[[], datetime]
_MAX_SAVE_ATTEMPTS = 2


class AuthService:
    def __init__(
        self,
        repo: Repository,
        tokens: TokenIssuer,
        verify: Callable[[str, str], bool],
        dummy_hash: str,
        clock: Clock,
    ) -> None:
        self._repo = repo
        self._tokens = tokens
        self._verify = verify
        self._dummy_hash = dummy_hash
        self._clock = clock

    def login(self, email: str, password: str) -> str:
        user = self._repo.get_user_by_email(email)
        if user is None:
            self._verify(password, self._dummy_hash)  # equalise timing with the real path
            raise InvalidCredentialsError("invalid credentials")
        if not self._verify(password, user.password_hash):
            raise InvalidCredentialsError("invalid credentials")
        return self._tokens.issue(user.id, now=self._clock())


@dataclass(frozen=True)
class CurrentCheckIns:
    draft: CheckIn | None
    latest_submitted: CheckIn | None


class CheckInService:
    def __init__(self, repo: Repository, clock: Clock) -> None:
        self._repo = repo
        self._clock = clock

    def current(self, user: User) -> CurrentCheckIns:
        return CurrentCheckIns(
            draft=self._repo.find_draft(user.id),
            latest_submitted=self._repo.find_latest_submitted(user.id),
        )

    def save_draft(
        self,
        user: User,
        *,
        connectedness: int | None,
        support: int | None,
        workload: int | None,
    ) -> CheckIn:
        for _ in range(_MAX_SAVE_ATTEMPTS):
            now = self._clock()
            draft = self._repo.find_draft(user.id, for_update=True)
            if draft is None:
                draft = CheckIn.start(
                    employee_id=user.id,
                    organization_id=user.organization_id,
                    team_id=user.team_id,
                    now=now,
                )
            draft.save_draft(
                now=now, connectedness=connectedness, support=support, workload=workload
            )
            try:
                self._repo.save(draft)
                self._repo.commit()
            except ConcurrentDraftError:
                # Another request created this employee's draft first. Re-read it and apply ours.
                self._repo.rollback()
                continue
            return draft
        raise ConcurrentDraftError("could not save the draft after a concurrent update")

    def submit(self, user: User, check_in_id: UUID) -> CheckIn:
        check_in = self._repo.find_by_id_for_employee(check_in_id, user.id, for_update=True)
        if check_in is None:
            raise NotFoundError("check-in not found")
        check_in.submit(now=self._clock())
        self._repo.save(check_in)
        self._repo.commit()
        return check_in

    def get(self, user: User, check_in_id: UUID) -> CheckIn:
        check_in = self._repo.find_by_id_for_employee(check_in_id, user.id)
        if check_in is None:
            raise NotFoundError("check-in not found")
        return check_in


class WellbeingService:
    def __init__(self, repo: Repository, month_start: datetime) -> None:
        self._repo = repo
        self._month_start = month_start

    def summary(self, user: User, team_id: UUID | None) -> WellbeingSummary:
        if team_id is not None and not self._repo.team_in_organization(
            team_id, user.organization_id
        ):
            raise NotFoundError("team not found")
        records = self._repo.submitted_records(user.organization_id, team_id)
        eligible = self._repo.eligible_count(user.organization_id, team_id)
        return summarize(records, eligible, self._month_start)

    def teams(self, user: User) -> list[tuple[UUID, str]]:
        return self._repo.list_teams(user.organization_id)
