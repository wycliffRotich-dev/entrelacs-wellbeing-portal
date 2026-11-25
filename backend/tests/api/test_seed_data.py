"""The demo dataset must exercise every aggregation rule the brief names, through the real API."""
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import DEMO_PASSWORD, HR_EMAILS, seed

MONTH = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
def seeded_client(connect, token_service, now) -> Iterator[TestClient]:
    with connect() as conn:
        assert seed(conn, reset=True) is True
    app = create_app(
        connection_factory=connect,
        token_service=token_service,
        clock=lambda: now,
        reporting_month_start=MONTH,
    )
    yield TestClient(app)
    with connect() as conn:
        conn.execute("truncate check_ins, users, teams, organizations cascade")


def login(client, org):
    r = client.post(
        "/api/auth/login", json={"email": HR_EMAILS[org], "password": DEMO_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demo_data_covers_every_aggregation_case(seeded_client):
    c = seeded_client
    h = login(c, "Northwind Health")
    teams = {t["name"]: t["id"] for t in c.get("/api/hr/teams", headers=h).json()}

    def summary(name):
        return c.get("/api/hr/wellbeing", params={"team_id": teams[name]}, headers=h).json()

    platform = summary("Platform")
    assert (platform["respondent_count"], platform["eligible_count"]) == (5, 7)
    assert platform["suppressed"] is False and platform["average_score"] == 72.7

    support = summary("Support")
    assert (support["respondent_count"], support["eligible_count"]) == (3, 4)
    assert support["suppressed"] is True and support["average_score"] is None

    design = summary("Design")
    assert (design["respondent_count"], design["eligible_count"]) == (0, 3)
    assert design["suppressed"] is True

    ops = summary("Ops")
    assert ops["eligible_count"] == 0 and ops["participation_rate"] is None

    overall = c.get("/api/hr/wellbeing", headers=h).json()
    assert (overall["respondent_count"], overall["eligible_count"]) == (8, 14)
    assert overall["suppressed"] is False


def test_second_organization_is_isolated(seeded_client):
    h = login(seeded_client, "Contoso Labs")
    body = seeded_client.get("/api/hr/wellbeing", headers=h).json()
    assert (body["respondent_count"], body["eligible_count"]) == (8, 9)
    assert {t["name"] for t in seeded_client.get("/api/hr/teams", headers=h).json()} == {
        "Engineering",
        "Sales",
    }
