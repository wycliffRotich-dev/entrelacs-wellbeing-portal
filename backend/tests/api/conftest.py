from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from app.main import create_app
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.domain.check_ins.score import calculate_score
from app.infrastructure.security.passwords import hash_password
from app.infrastructure.security.tokens import TokenService

ROOT = Path(__file__).resolve().parents[3]
PASSWORD = "correct-horse-battery"
SECRET = "t" * 64
FIXED_NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
MONTH_START = datetime(2026, 10, 1, tzinfo=UTC)
TRUNCATE = "truncate check_ins, users, teams, organizations cascade"
_PASSWORD_HASH = hash_password(PASSWORD)


def _connect():
    password = (ROOT / "secrets" / "postgres_password").read_text(encoding="utf-8").strip()
    return psycopg.connect(
        host="127.0.0.1", port=5433, dbname="wellbeing_test", user="wellbeing",
        password=password, row_factory=dict_row,
    )


class World:
    """Org A: teams A1 (e1-e5), A2 (e6-e7), A3 (empty), hr_a. Org B: team B1 (b1), hr_b."""

    def __init__(self):
        self.orgs, self.teams, self.users = {}, {}, {}

    def user_id(self, key):
        return self.users[key]["id"]

    def email(self, key):
        return self.users[key]["email"]

    def execute(self, sql, params=()):
        with _connect() as conn:
            conn.execute(sql, params)

    def add_submitted(self, key, at, answers=(5, 5, 5)):
        u = self.users[key]
        c, s, w = answers
        self.execute(
            "insert into check_ins (id, employee_id, organization_id, team_id, connectedness,"
            " support, workload, score, status, created_at, updated_at, submitted_at)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s, %s, %s)",
            (uuid4(), u["id"], u["org"], u["team"], c, s, w, calculate_score(c, s, w), at, at, at),
        )

    def add_draft(self, key, at):
        u = self.users[key]
        self.execute(
            "insert into check_ins (id, employee_id, organization_id, team_id, status,"
            " created_at, updated_at) values (%s, %s, %s, %s, 'DRAFT', %s, %s)",
            (uuid4(), u["id"], u["org"], u["team"], at, at),
        )


def _seed(world):
    with _connect() as conn:
        for name in ("A", "B"):
            world.orgs[name] = uuid4()
            conn.execute("insert into organizations (id, name) values (%s, %s)",
                         (world.orgs[name], f"Org {name}"))
        for key, org, name in (("A1", "A", "Alpha"), ("A2", "A", "Bravo"),
                               ("A3", "A", "Charlie"), ("B1", "B", "Delta")):
            world.teams[key] = uuid4()
            conn.execute("insert into teams (id, organization_id, name) values (%s, %s, %s)",
                         (world.teams[key], world.orgs[org], name))
        spec: list[tuple[str, str, str | None, str]] = [(f"e{i}", "A", "A1", "EMPLOYEE") for i in range(1, 6)]
        spec += [("e6", "A", "A2", "EMPLOYEE"), ("e7", "A", "A2", "EMPLOYEE"),
                 ("hr_a", "A", None, "HR"), ("b1", "B", "B1", "EMPLOYEE"), ("hr_b", "B", None, "HR")]
        for key, org, team, role in spec:
            uid, email = uuid4(), f"{key}@example.test"
            org_id = world.orgs[org]
            team_id = world.teams[team] if team else None
            conn.execute(
                "insert into users (id, organization_id, team_id, email, password_hash, role)"
                " values (%s, %s, %s, %s, %s, %s)",
                (uid, org_id, team_id, email, _PASSWORD_HASH, role),
            )
            world.users[key] = {"id": uid, "email": email, "org": org_id, "team": team_id}


@pytest.fixture
def world():
    with _connect() as conn:
        conn.execute(TRUNCATE)
    w = World()
    _seed(w)
    yield w
    with _connect() as conn:
        conn.execute(TRUNCATE)


@pytest.fixture
def token_service():
    return TokenService(SECRET, timedelta(minutes=30))


@pytest.fixture
def now():
    return FIXED_NOW


@pytest.fixture
def password():
    return PASSWORD


@pytest.fixture
def client(world, token_service):
    app = create_app(
        connection_factory=_connect,
        token_service=token_service,
        clock=lambda: FIXED_NOW,
        reporting_month_start=MONTH_START,
    )
    return TestClient(app)


@pytest.fixture
def login(client, world):
    def _login(key):
        r = client.post("/api/auth/login", json={"email": world.email(key), "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login
