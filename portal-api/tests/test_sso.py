import time

import pytest
from jose import jwk, jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.config import get_settings
from app.services import sso
from app.services.rate_limit import login_limiter


@pytest.fixture()
def app_sso_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_sso_secret", "test-shared-secret-for-sso-1234567890")
    return s


def _assertion(sub="T-MA", jti="j1", lifetime=60, secret="test-shared-secret-for-sso-1234567890", iss="mitarbeiter-app"):
    now = int(time.time())
    return jwt.encode({"iss": iss, "sub": sub, "jti": jti, "iat": now, "exp": now + lifetime}, secret, algorithm="HS256")


def test_app_sso_disabled_by_default(client, seeded_users):
    r = client.post("/auth/app-sso", json={"assertion": _assertion()})
    assert r.status_code == 401


def test_app_sso_login_and_replay_protection(client, seeded_users, app_sso_on):
    a = _assertion()
    r = client.post("/auth/app-sso", json={"assertion": a})
    assert r.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).json()
    assert me["personalnummer"] == "T-MA"
    # gleiche Assertion ein zweites Mal -> abgelehnt
    assert client.post("/auth/app-sso", json={"assertion": a}).status_code == 401


def test_app_sso_rejects_bad_signature_issuer_lifetime_unknown(client, seeded_users, app_sso_on):
    for a in (
        _assertion(jti="a", secret="wrong-secret-wrong-secret-wrong-secret"),
        _assertion(jti="b", iss="evil"),
        _assertion(jti="c", lifetime=3600),
        _assertion(jti="d", lifetime=-5),
        _assertion(jti="e", sub="NOPE"),
    ):
        assert client.post("/auth/app-sso", json={"assertion": a}).status_code == 401
        login_limiter.reset("ip:testclient")


def test_oidc_flow_with_mock_idp(client, seeded_users, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "oidc_enabled", True)
    monkeypatch.setattr(s, "oidc_issuer", "https://idp.example.test/tenant")
    monkeypatch.setattr(s, "oidc_client_id", "cid")
    monkeypatch.setattr(s, "oidc_client_secret", "sec")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pub = jwk.construct(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(), "RS256").to_dict()
    pub["kid"] = "k1"
    disc = {
        "issuer": "https://idp.example.test/tenant", "authorization_endpoint": "https://idp.example.test/auth",
        "token_endpoint": "https://idp.example.test/token", "jwks_uri": "https://idp.example.test/jwks",
    }
    box = {}

    def get_json(url):
        return {"keys": [pub]} if url.endswith("/jwks") else disc

    def post_form(url, data):
        box["id_token"] = jwt.encode(
            {"iss": disc["issuer"], "aud": "cid", "nonce": box["nonce"], "email": "T-MA@example.test",
             "exp": int(time.time()) + 300}, pem, algorithm="RS256", headers={"kid": "k1"})
        return {"id_token": box["id_token"]}

    monkeypatch.setattr(sso, "_get_json", get_json)
    monkeypatch.setattr(sso, "_post_form", post_form)

    from app.models.person import Person
    db = client.app.dependency_overrides[__import__("app.db", fromlist=["get_db"]).get_db]().__next__()
    db.query(Person).filter_by(personalnummer="T-MA").one().email = "T-MA@example.test"
    db.commit()

    url = client.get("/auth/oidc/login").json()["url"]
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(url).query)
    box["nonce"] = q["nonce"][0]
    r = client.post("/auth/oidc/callback", json={"code": "abc", "state": q["state"][0]})
    assert r.status_code == 200, r.text
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).json()["personalnummer"] == "T-MA"
    # falscher State
    assert client.post("/auth/oidc/callback", json={"code": "abc", "state": "x"}).status_code == 401
