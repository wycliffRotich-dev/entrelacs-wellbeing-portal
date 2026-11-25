from uuid import uuid4

from app.presentation.errors import _MAPPED  # noqa: F401  (import check: handlers exist)

CURRENT = "/api/employee/check-ins/current"


def _code(response):
    return response.json()["error"]["code"]


def test_non_validation_errors_carry_code_and_message_only(client, login):
    h = login("e1")
    cases = [
        (client.get(CURRENT), 401, "not_authenticated"),
        (client.get("/api/hr/wellbeing", headers=h), 403, "forbidden"),
        (client.get(f"/api/employee/check-ins/{uuid4()}", headers=h), 404, "not_found"),
    ]
    for response, status, expected_code in cases:
        assert response.status_code == status
        assert set(response.json()) == {"error"}
        assert set(response.json()["error"]) == {"code", "message"}
        assert _code(response) == expected_code


def test_validation_errors_add_details_with_field_and_message(client, login):
    r = client.get("/api/employee/check-ins/not-a-uuid", headers=login("e1"))
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert set(error) == {"code", "message", "details"}
    assert error["details"]
    assert all(set(item) == {"field", "message"} for item in error["details"])
