"""HTTP routes. Authorization is enforced by dependencies before any lookup happens."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.services import AuthService, CheckInService, WellbeingService
from app.domain.users import User
from app.presentation.dependencies import (
    CurrentUser,
    get_auth_service,
    get_check_in_service,
    get_wellbeing_service,
    require_employee,
    require_hr,
)
from app.presentation.schemas import (
    CheckInResponse,
    CurrentCheckInsResponse,
    DraftRequest,
    LoginRequest,
    MeResponse,
    TeamResponse,
    TokenResponse,
    WellbeingResponse,
)

router = APIRouter(prefix="/api")

Employee = Annotated[User, Depends(require_employee)]
HrUser = Annotated[User, Depends(require_hr)]
AuthSvc = Annotated[AuthService, Depends(get_auth_service)]
CheckInSvc = Annotated[CheckInService, Depends(get_check_in_service)]
WellbeingSvc = Annotated[WellbeingService, Depends(get_wellbeing_service)]


@router.post("/auth/login")
def login(body: LoginRequest, auth: AuthSvc) -> TokenResponse:
    return TokenResponse(access_token=auth.login(body.email, body.password))


@router.get("/auth/me")
def me(user: CurrentUser) -> MeResponse:
    return MeResponse.from_domain(user)


@router.get("/employee/check-ins/current")
def current_check_ins(user: Employee, svc: CheckInSvc) -> CurrentCheckInsResponse:
    current = svc.current(user)
    return CurrentCheckInsResponse(
        draft=CheckInResponse.from_domain(current.draft) if current.draft else None,
        latest_submitted=(
            CheckInResponse.from_domain(current.latest_submitted)
            if current.latest_submitted
            else None
        ),
    )


@router.put("/employee/check-ins/draft")
def save_draft(body: DraftRequest, user: Employee, svc: CheckInSvc) -> CheckInResponse:
    draft = svc.save_draft(
        user,
        connectedness=body.connectedness,
        support=body.support,
        workload=body.workload,
    )
    return CheckInResponse.from_domain(draft)


@router.post("/employee/check-ins/{check_in_id}/submit")
def submit_check_in(check_in_id: UUID, user: Employee, svc: CheckInSvc) -> CheckInResponse:
    return CheckInResponse.from_domain(svc.submit(user, check_in_id))


@router.get("/employee/check-ins/{check_in_id}")
def get_check_in(check_in_id: UUID, user: Employee, svc: CheckInSvc) -> CheckInResponse:
    return CheckInResponse.from_domain(svc.get(user, check_in_id))


@router.get("/hr/wellbeing")
def wellbeing(
    request: Request, user: HrUser, svc: WellbeingSvc, team_id: UUID | None = None
) -> WellbeingResponse:
    summary = svc.summary(user, team_id)
    return WellbeingResponse.from_domain(summary, request.app.state.reporting_month_start, team_id)


@router.get("/hr/teams")
def teams(user: HrUser, svc: WellbeingSvc) -> list[TeamResponse]:
    return [TeamResponse(id=team_id, name=name) for team_id, name in svc.teams(user)]
