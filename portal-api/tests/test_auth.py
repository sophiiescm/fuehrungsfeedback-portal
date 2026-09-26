from fastapi import HTTPException
import pytest

from app.api.deps import CurrentUser, require_role
from app.models.person import Role


def test_dev_login_users_lists_seeded_persons(client, seeded_users):
    response = client.get("/auth/dev-login/users")
    assert response.status_code == 200
    by_personalnummer = {u["personalnummer"]: u for u in response.json()}
    assert by_personalnummer["T-ADMIN"]["roles"] == ["admin"]
    assert by_personalnummer["T-FK"]["roles"] == ["fuehrungskraft"]
    assert by_personalnummer["T-MA"]["roles"] == ["mitarbeiter"]


def test_dev_login_and_me_roundtrip(client, seeded_users):
    login_response = client.post("/auth/dev-login", json={"personalnummer": "T-FK"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["personalnummer"] == "T-FK"
    assert body["roles"] == ["fuehrungskraft"]


def test_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_dev_login_unknown_person_returns_404(client, seeded_users):
    response = client.post("/auth/dev-login", json={"personalnummer": "DOES-NOT-EXIST"})
    assert response.status_code == 404


class _GetRequest:
    method = "GET"


def test_require_role_allows_matching_role(seeded_users):
    current = CurrentUser(person=seeded_users["admin"], roles=[Role.admin])
    dependency = require_role(Role.admin)
    assert dependency(request=_GetRequest(), current_user=current, db=None) is current


def test_require_role_rejects_missing_role(seeded_users):
    current = CurrentUser(person=seeded_users["employee"], roles=[Role.mitarbeiter])
    dependency = require_role(Role.admin, Role.fuehrungskraft)
    with pytest.raises(HTTPException) as exc_info:
        dependency(request=_GetRequest(), current_user=current, db=None)
    assert exc_info.value.status_code == 403
