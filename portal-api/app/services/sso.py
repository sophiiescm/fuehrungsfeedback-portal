"""Anmeldung ohne Passwort: Trusted-App-SSO (Mitarbeiter-App) und OIDC (Entra ID).

Trusted-App-SSO: Die Mitarbeiter-App (in der die Person bereits angemeldet ist) erzeugt
eine kurzlebige, mit einem gemeinsamen Geheimnis (HS256) signierte Assertion:
  iss = app_sso_issuer, sub = Personalnummer, iat/exp (max. app_sso_max_lifetime_seconds),
  jti = Einmal-ID. Das Portal loest jede jti nur einmal ein.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.core.config import get_settings
from app.models.person import Person, RoleAssignment
from app.models.sso import UsedAssertion


class SsoError(Exception):
    pass


def issue_token(db: Session, person: Person) -> str:
    roles = db.execute(select(RoleAssignment.role).where(RoleAssignment.person_id == person.id)).scalars().all()
    return create_access_token(person.id, [r.value for r in roles])


def verify_app_assertion(db: Session, assertion: str) -> Person:
    s = get_settings()
    if not s.app_sso_secret:
        raise SsoError("Trusted-App-SSO ist nicht aktiviert")
    try:
        claims = jwt.decode(assertion, s.app_sso_secret, algorithms=["HS256"], issuer=s.app_sso_issuer)
    except JWTError as exc:
        raise SsoError("Assertion ungültig oder abgelaufen") from exc
    jti, sub, exp, iat = claims.get("jti"), claims.get("sub"), claims.get("exp"), claims.get("iat")
    if not jti or not sub or not exp or not iat:
        raise SsoError("Assertion unvollständig")
    if exp - iat > s.app_sso_max_lifetime_seconds:
        raise SsoError("Assertion zu lange gültig")
    now = datetime.now(timezone.utc)
    db.execute(delete(UsedAssertion).where(UsedAssertion.expires_at < now))
    if db.get(UsedAssertion, str(jti)) is not None:
        raise SsoError("Assertion wurde bereits verwendet")
    person = db.execute(select(Person).where(Person.personalnummer == str(sub))).scalar_one_or_none()
    if person is None or not person.aktiv:
        raise SsoError("Person unbekannt oder inaktiv")
    db.add(UsedAssertion(jti=str(jti), expires_at=datetime.fromtimestamp(exp, timezone.utc)))
    db.commit()
    return person


# --- OIDC (Entra ID u. a.) -------------------------------------------------

def _get_json(url: str) -> dict:
    return httpx.get(url, timeout=10).raise_for_status().json()


def _post_form(url: str, data: dict) -> dict:
    return httpx.post(url, data=data, timeout=10).raise_for_status().json()


def _discovery() -> dict:
    s = get_settings()
    return _get_json(f"{s.oidc_issuer.rstrip('/')}/.well-known/openid-configuration")


def oidc_authorization_url() -> str:
    s = get_settings()
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, s.secret_key, algorithm="HS256"
    )
    query = urlencode({
        "client_id": s.oidc_client_id, "response_type": "code", "scope": "openid email profile",
        "redirect_uri": s.oidc_redirect_url, "state": state, "nonce": nonce,
    })
    return f"{_discovery()['authorization_endpoint']}?{query}"


def oidc_complete(db: Session, code: str, state: str) -> Person:
    s = get_settings()
    try:
        nonce = jwt.decode(state, s.secret_key, algorithms=["HS256"])["nonce"]
    except (JWTError, KeyError) as exc:
        raise SsoError("Ungültiger State") from exc
    disc = _discovery()
    tokens = _post_form(disc["token_endpoint"], {
        "grant_type": "authorization_code", "code": code, "redirect_uri": s.oidc_redirect_url,
        "client_id": s.oidc_client_id, "client_secret": s.oidc_client_secret,
    })
    try:
        claims = jwt.decode(
            tokens["id_token"], _get_json(disc["jwks_uri"]), algorithms=["RS256"],
            audience=s.oidc_client_id, issuer=disc.get("issuer", s.oidc_issuer),
            options={"verify_at_hash": False},
        )
    except (JWTError, KeyError) as exc:
        raise SsoError("ID-Token ungültig") from exc
    if claims.get("nonce") != nonce:
        raise SsoError("Nonce stimmt nicht überein")
    value = claims.get(s.oidc_person_claim)
    if not value:
        raise SsoError(f"Claim '{s.oidc_person_claim}' fehlt im ID-Token")
    col = Person.personalnummer if s.oidc_person_field == "personalnummer" else Person.email
    person = db.execute(select(Person).where(col.ilike(str(value)))).scalar_one_or_none()
    if person is None or not person.aktiv:
        raise SsoError("Keine passende aktive Person im Portal")
    return person
