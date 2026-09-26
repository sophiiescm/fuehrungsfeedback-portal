"""Nur fuer die Entwicklung (APP_ENV=dev): Schnellzugriff auf typische Ansichten und Simulator
der Mitarbeiter-App (stellt Trusted-App-SSO-Assertions aus). In Produktion antworten alle Routen mit 404."""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models.person import Person, Role, RoleAssignment
from app.models.round import Participation, ParticipationStatus

router = APIRouter(prefix="/dev", tags=["dev"])


def _dev_only() -> None:
    if get_settings().app_env != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht verfuegbar")


def _has_role(db: Session, person_id: int, role: Role) -> bool:
    return db.execute(select(RoleAssignment.id).where(RoleAssignment.person_id == person_id, RoleAssignment.role == role)).first() is not None


def _persona(p: Person | None, title: str, note: str) -> dict | None:
    return None if p is None else {"title": title, "personalnummer": p.personalnummer, "full_name": p.full_name, "note": note}


@router.get("/personas", dependencies=[Depends(_dev_only)])
def personas(db: Session = Depends(get_db)) -> list[dict]:
    """Je Rolle eine sinnvolle Beispielperson: Admin, Fuehrungskraft, Mitarbeiter (mit offenem Feedback
    bevorzugt) und Produktions-Mitarbeiter ohne E-Mail (Code-Brief bzw. Mitarbeiter-App-SSO)."""
    active = db.execute(select(Person).where(Person.aktiv.is_(True), Person.personalnummer.not_like("DEV-%")).order_by(Person.id)).scalars().all()
    reports_of = {}
    for p in active:
        if p.manager_personalnummer:
            reports_of[p.manager_personalnummer] = reports_of.get(p.manager_personalnummer, 0) + 1
    is_leader = lambda p: p.personalnummer in reports_of  # noqa: E731
    admin = next((p for p in active if _has_role(db, p.id, Role.admin)), None)
    fk = next((p for p in active if is_leader(p) and reports_of[p.personalnummer] >= 3 and p != admin and p.manager_personalnummer), None)
    open_ids = set(db.execute(select(Participation.person_id).where(Participation.status == ParticipationStatus.offen)).scalars())
    ma = next((p for p in active if not is_leader(p) and p.id in open_ids), None) or \
        next((p for p in active if not is_leader(p) and p.email and reports_of.get(p.manager_personalnummer, 0) >= 3), None)
    prod = next((p for p in active if not is_leader(p) and not p.email and reports_of.get(p.manager_personalnummer, 0) >= 3), None)
    out = [
        _persona(admin, "Admin (HR)", "Verwaltung, Runden, Auswertung"),
        _persona(fk, "Führungskraft", "Report, Trend, Maßnahmen"),
        _persona(ma, "Mitarbeiter", "Feedback abgeben, Maßnahmen des Teams"),
        _persona(prod, "Produktion ohne E-Mail", "Code-Brief bzw. Mitarbeiter-App-SSO"),
    ]
    return [x for x in out if x]


class AssertionIn(BaseModel):
    personalnummer: str


@router.post("/app-assertion", dependencies=[Depends(_dev_only)])
def app_assertion(payload: AssertionIn, db: Session = Depends(get_db)) -> dict:
    """Simuliert die Mitarbeiter-App: erzeugt die signierte Einmal-Assertion fuer Trusted-App-SSO."""
    s = get_settings()
    if not s.app_sso_secret:
        raise HTTPException(status.HTTP_409_CONFLICT, "APP_SSO_SECRET ist nicht gesetzt")
    person = db.execute(select(Person).where(Person.personalnummer == payload.personalnummer, Person.aktiv.is_(True))).scalar_one_or_none()
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")
    now = int(time.time())
    token = jwt.encode(
        {"iss": s.app_sso_issuer, "sub": person.personalnummer, "iat": now, "exp": now + 60, "jti": uuid.uuid4().hex},
        s.app_sso_secret, algorithm="HS256",
    )
    return {"assertion": token, "portal_url": f"{s.portal_public_url}/sso#assertion={token}"}
