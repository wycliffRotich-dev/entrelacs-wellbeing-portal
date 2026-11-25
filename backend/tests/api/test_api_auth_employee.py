from datetime import timedelta
from uuid import uuid4

import pytest

DRAFT = "/api/employee/check-ins/draft"
CURRENT = "/api/employee/check-ins/current"


def save(client, headers, **answers):
    return client.put(DRAFT, json=answers, headers=headers)


def code(response):
    return response.json()["error"]["code"]


# --- authentication ---------------------------------------------------------------------
def test_login_succeeds_and_email_is_case_insensitive(client, world, password):
    r = client.post("/api/auth/login", json={"email": world.email("e1").upper(), "password": password})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer" and r.json()["access_token"]


def test_login_failures_are_indistinguishable(client, world):
    wrong = client.post("/api/auth/login", json={"email": world.email("e1"), "password": "nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.test", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert code(wrong) == "invalid_credentials"


def test_me_returns_identity_from_the_database_without_secrets(client, world, login):
    body = client.get("/api/auth/me", headers=login("hr_a")).json()
    assert set(body) == {"id", "email", "role", "organization_id", "team_id"}
    assert body["role"] == "HR" and body["organization_id"] == str(world.orgs["A"])
    assert body["team_id"] is None


def test_garbage_token_is_rejected(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and code(r) == "not_authenticated"


def test_expired_token_is_rejected(client, world, token_service, now):
    token = token_service.issue(world.user_id("e1"), now=now - timedelta(hours=2))
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_for_a_deleted_user_is_rejected(client, world, login):
    headers = login("b1")
    world.execute("delete from users where id = %s", (world.user_id("b1"),))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/auth/me"),
        ("GET", CURRENT),
        ("PUT", DRAFT),
        ("POST", f"/api/employee/check-ins/{uuid4()}/submit"),
        ("GET", f"/api/employee/check-ins/{uuid4()}"),
        ("GET", "/api/hr/wellbeing"),
        ("GET", "/api/hr/teams"),
    ],
)
def test_every_protected_endpoint_requires_authentication(client, method, path):
    r = client.request(method, path, json={} if method == "PUT" else None)
    assert r.status_code == 401


# --- employee check-in lifecycle -------------------------------------------------------
def test_new_employee_has_no_draft_and_no_submission(client, login):
    r = client.get(CURRENT, headers=login("e1"))
    assert r.status_code == 200
    assert r.json() == {"draft": None, "latest_submitted": None}


def test_partial_draft_is_saved_and_resumed(client, login):
    h = login("e1")
    saved = save(client, h, connectedness=7)
    assert saved.status_code == 200
    assert saved.json()["status"] == "DRAFT" and saved.json()["score"] is None
    draft = client.get(CURRENT, headers=h).json()["draft"]
    assert draft["id"] == saved.json()["id"]
    assert (draft["connectedness"], draft["support"], draft["workload"]) == (7, None, None)


def test_saving_again_updates_the_same_draft(client, login):
    h = login("e1")
    first = save(client, h, connectedness=7).json()
    second = save(client, h, support=3).json()
    assert first["id"] == second["id"]
    assert (second["connectedness"], second["support"]) == (7, 3)


@pytest.mark.parametrize("bad", [11, -1, 7.5, "7", True])
def test_invalid_answers_are_rejected(client, login, bad):
    h = login("e1")
    assert save(client, h, connectedness=bad).status_code == 422
    assert client.get(CURRENT, headers=h).json()["draft"] is None


def test_client_cannot_choose_ownership_or_score(client, world, login):
    h = login("e1")
    r = client.put(
        DRAFT,
        json={
            "connectedness": 5,
            "employee_id": str(world.user_id("e2")),
            "organization_id": str(world.orgs["B"]),
            "team_id": str(world.teams["B1"]),
            "score": 100,
        },
        headers=h,
    )
    assert r.status_code == 422
    assert client.get(CURRENT, headers=h).json()["draft"] is None


def test_draft_is_owned_by_the_authenticated_employee(client, world, login):
    save(client, login("e1"), connectedness=5)
    row = None
    with __import__("tests.api.conftest", fromlist=["_connect"])._connect() as conn:
        row = conn.execute("select employee_id, organization_id, team_id from check_ins").fetchone()
    assert row["employee_id"] == world.user_id("e1")
    assert row["organization_id"] == world.orgs["A"] and row["team_id"] == world.teams["A1"]


def test_submit_requires_all_answers(client, login):
    h = login("e1")
    draft = save(client, h, connectedness=5, support=5).json()
    r = client.post(f"/api/employee/check-ins/{draft['id']}/submit", headers=h)
    assert r.status_code == 422 and code(r) == "incomplete_check_in"
    assert client.get(CURRENT, headers=h).json()["draft"]["status"] == "DRAFT"


def test_submit_calculates_the_score_on_the_server(client, login):
    h = login("e1")
    draft = save(client, h, connectedness=10, support=10, workload=9).json()
    r = client.post(f"/api/employee/check-ins/{draft['id']}/submit", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "SUBMITTED" and r.json()["score"] == 96.7
    current = client.get(CURRENT, headers=h).json()
    assert current["draft"] is None and current["latest_submitted"]["id"] == draft["id"]
    assert client.get(f"/api/employee/check-ins/{draft['id']}", headers=h).json()["score"] == 96.7


def test_second_submit_is_a_conflict(client, login):
    h = login("e1")
    draft = save(client, h, connectedness=5, support=5, workload=5).json()
    url = f"/api/employee/check-ins/{draft['id']}/submit"
    assert client.post(url, headers=h).status_code == 200
    again = client.post(url, headers=h)
    assert again.status_code == 409 and code(again) == "check_in_already_submitted"


def test_saving_after_submission_starts_a_new_draft_and_leaves_the_submission_intact(client, login):
    h = login("e1")
    done = save(client, h, connectedness=10, support=10, workload=10).json()
    client.post(f"/api/employee/check-ins/{done['id']}/submit", headers=h)
    new = save(client, h, connectedness=1).json()
    assert new["id"] != done["id"] and new["status"] == "DRAFT"
    kept = client.get(f"/api/employee/check-ins/{done['id']}", headers=h).json()
    assert kept["connectedness"] == 10 and kept["score"] == 100.0


# --- isolation between users and roles --------------------------------------------------
def test_employee_cannot_read_or_submit_another_employees_check_in(client, login):
    draft = save(client, login("e1"), connectedness=5, support=5, workload=5).json()
    other = login("e2")
    unknown = uuid4()
    read = client.get(f"/api/employee/check-ins/{draft['id']}", headers=other)
    submit = client.post(f"/api/employee/check-ins/{draft['id']}/submit", headers=other)
    missing = client.get(f"/api/employee/check-ins/{unknown}", headers=other)
    assert read.status_code == submit.status_code == missing.status_code == 404
    assert read.json() == missing.json()
    assert client.get(CURRENT, headers=login("e1")).json()["draft"]["status"] == "DRAFT"


def test_employee_in_another_organization_cannot_read_a_check_in(client, login):
    draft = save(client, login("e1"), connectedness=5).json()
    r = client.get(f"/api/employee/check-ins/{draft['id']}", headers=login("b1"))
    assert r.status_code == 404


def test_malformed_check_in_id_is_a_validation_error(client, login):
    r = client.get("/api/employee/check-ins/not-a-uuid", headers=login("e1"))
    assert r.status_code == 422


def test_hr_cannot_use_employee_endpoints(client, login):
    h = login("hr_a")
    assert client.get(CURRENT, headers=h).status_code == 403
    assert client.put(DRAFT, json={"connectedness": 5}, headers=h).status_code == 403
    assert code(client.get(CURRENT, headers=h)) == "forbidden"


def test_hr_cannot_fetch_an_individual_check_in_even_with_its_id(client, login):
    draft = save(client, login("e1"), connectedness=5, support=5, workload=5).json()
    r = client.get(f"/api/employee/check-ins/{draft['id']}", headers=login("hr_a"))
    assert r.status_code == 403


def test_employee_cannot_use_hr_endpoints(client, login):
    h = login("e1")
    assert client.get("/api/hr/wellbeing", headers=h).status_code == 403
    assert client.get("/api/hr/teams", headers=h).status_code == 403
