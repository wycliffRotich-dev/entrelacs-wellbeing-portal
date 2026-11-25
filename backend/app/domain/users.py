"""User identity as the domain sees it. Role and tenant are always loaded from the database."""
from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class Role(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    HR = "HR"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    organization_id: UUID
    team_id: UUID | None
    email: str
    password_hash: str
    role: Role
