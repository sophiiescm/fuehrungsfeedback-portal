"""Rechtepruefung pro Endpunkt (CLAUDE.md Qualitaet): jeder Endpunkt ausser der
bewussten Oeffentlich-Liste verlangt Anmeldung, Admin-Endpunkte die Admin-Rolle."""

import re

from app.main import app

PUBLIC = {"/health", "/auth/dev-login", "/auth/dev-login/users", "/auth/code-login", "/auth/oidc/login", "/auth/oidc/callback", "/auth/app-sso", "/auth/methods", "/dev/personas", "/dev/app-assertion",
          "/feedbacks/webhook/limesurvey-complete"}
ADMIN_PREFIXES = ("/organisation", "/surveys", "/rounds", "/mail-templates", "/benchmark", "/access")


def _routes():
    for r in app.routes:
        if hasattr(r, "methods") and r.path not in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                yield m, re.sub(r"\{[^}]+\}", "1", r.path), r.path


def test_all_non_public_endpoints_require_authentication(client):
    for method, path, template in _routes():
        if template in PUBLIC:
            continue
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {template} ohne Login -> {resp.status_code}"


def test_admin_endpoints_reject_normal_employee(client, seeded_users):
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-MA"}).json()["access_token"]}
    for method, path, template in _routes():
        if template in PUBLIC or not template.startswith(ADMIN_PREFIXES):
            continue
        resp = client.request(method, path, headers=h)
        assert resp.status_code == 403, f"{method} {template} als Mitarbeiter -> {resp.status_code}"
