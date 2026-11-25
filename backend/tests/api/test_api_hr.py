from datetime import UTC, datetime
from uuid import uuid4

import pytest

WELLBEING = "/api/hr/wellbeing"
EXPECTED_KEYS = {
    "reporting_month", "team_id", "respondent_count", "eligible_count",
    "participation_rate", "average_score", "suppressed",
}


def day(d, month=10):
    return datetime(2026, month, d, 12, 0, tzinfo=UTC)


def submit_all(world, keys, at=None, answers=(7, 7, 7)):
    for k in keys:
        world.add_submitted(k, at or day(5), answers)


def test_fewer_than_five_respondents_withholds_the_average(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4"])
    r = client.get(WELLBEING, params={"team_id": str(world.teams["A1"])}, headers=login("hr_a"))
    body = r.json()
    assert r.status_code == 200
    assert body["suppressed"] is True and body["average_score"] is None
    assert (body["respondent_count"], body["eligible_count"]) == (4, 5)
    assert body["participation_rate"] == 80.0
    assert "70.0" not in r.text  # the real average must not appear anywhere in the response


def test_five_respondents_reveals_the_average(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4", "e5"])
    body = client.get(WELLBEING, params={"team_id": str(world.teams["A1"])}, headers=login("hr_a")).json()
    assert body["suppressed"] is False and body["average_score"] == 70.0
    assert body["respondent_count"] == 5 and body["participation_rate"] == 100.0


def test_organization_overview_combines_all_teams(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4", "e5", "e6", "e7"])
    body = client.get(WELLBEING, headers=login("hr_a")).json()
    assert body["team_id"] is None and body["reporting_month"] == "2026-10"
    assert (body["respondent_count"], body["eligible_count"]) == (7, 7)
    assert body["participation_rate"] == 100.0 and body["average_score"] == 70.0


def test_organization_with_few_respondents_is_suppressed_too(client, world, login):
    submit_all(world, ["e6", "e7"])
    body = client.get(WELLBEING, headers=login("hr_a")).json()
    assert body["suppressed"] is True and body["average_score"] is None
    assert body["respondent_count"] == 2 and body["participation_rate"] == pytest.approx(28.6)


def test_latest_submission_per_employee_counts_once(client, world, login):
    world.add_submitted("e1", day(3), (10, 10, 10))
    world.add_submitted("e1", day(20), (0, 0, 0))
    submit_all(world, ["e2", "e3", "e4", "e5"], answers=(5, 5, 5))
    body = client.get(WELLBEING, params={"team_id": str(world.teams["A1"])}, headers=login("hr_a")).json()
    assert body["respondent_count"] == 5
    assert body["average_score"] == 40.0  # (0 + 4 * 50) / 5


def test_drafts_and_other_months_are_excluded(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4"])
    world.add_draft("e5", day(9))
    world.add_submitted("e5", day(28, month=9))
    world.add_submitted("e5", day(1, month=11))
    body = client.get(WELLBEING, params={"team_id": str(world.teams["A1"])}, headers=login("hr_a")).json()
    assert body["respondent_count"] == 4 and body["suppressed"] is True


def test_team_without_employees_has_no_participation_rate(client, world, login):
    body = client.get(WELLBEING, params={"team_id": str(world.teams["A3"])}, headers=login("hr_a")).json()
    assert body["eligible_count"] == 0 and body["participation_rate"] is None
    assert body["respondent_count"] == 0 and body["suppressed"] is True


def test_hr_cannot_filter_by_another_organizations_team(client, world, login):
    h = login("hr_a")
    foreign = client.get(WELLBEING, params={"team_id": str(world.teams["B1"])}, headers=h)
    unknown = client.get(WELLBEING, params={"team_id": str(uuid4())}, headers=h)
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()


def test_hr_only_sees_their_own_organization(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4", "e5"])
    world.add_submitted("b1", day(6), (3, 3, 3))
    b = client.get(WELLBEING, headers=login("hr_b")).json()
    assert (b["respondent_count"], b["eligible_count"]) == (1, 1)
    assert b["suppressed"] is True and b["average_score"] is None
    a = client.get(WELLBEING, headers=login("hr_a")).json()
    assert a["respondent_count"] == 5 and a["eligible_count"] == 7


def test_malformed_team_filter_is_a_validation_error(client, login):
    r = client.get(WELLBEING, params={"team_id": "not-a-uuid"}, headers=login("hr_a"))
    assert r.status_code == 422


def test_team_list_contains_only_own_organization(client, world, login):
    teams = client.get("/api/hr/teams", headers=login("hr_a")).json()
    assert {t["name"] for t in teams} == {"Alpha", "Bravo", "Charlie"}
    assert all(set(t) == {"id", "name"} for t in teams)


def test_response_contains_no_individual_data(client, world, login):
    submit_all(world, ["e1", "e2", "e3", "e4", "e5"])
    r = client.get(WELLBEING, headers=login("hr_a"))
    assert set(r.json()) == EXPECTED_KEYS
    for user in world.users.values():
        assert str(user["id"]) not in r.text and user["email"] not in r.text
    for word in ("connectedness", "support", "workload", "employee"):
        assert word not in r.text.lower()
