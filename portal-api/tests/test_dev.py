import time

from jose import jwt

from app.core.config import get_settings


def test_dev_personas_and_app_assertion_roundtrip(client, seeded_users, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_sso_secret", "dev-secret-for-test-abcdefghijklmnop")
    p = client.get("/dev/personas").json()
    assert p and p[0]["title"].startswith("Admin")
    a = client.post("/dev/app-assertion", json={"personalnummer": "T-MA"}).json()
    r = client.post("/auth/app-sso", json={"assertion": a["assertion"]})
    assert r.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).json()
    assert me["personalnummer"] == "T-MA"
    assert jwt.get_unverified_claims(a["assertion"])["exp"] - int(time.time()) <= 61


def test_dev_endpoints_hidden_in_prod(client, seeded_users, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    assert client.get("/dev/personas").status_code == 404
    assert client.post("/dev/app-assertion", json={"personalnummer": "T-MA"}).status_code == 404
