"""Feingranulare Admin-Rechte ueber frei anlegbare Zugriffsrollen.

`Role.admin` (RoleAssignment) bedeutet nur "hat Zugang zum Verwaltungsbereich". Was die Person dort
darf, ergibt sich aus den zugewiesenen Zugriffsrollen (Vereinigung ihrer Rechte). Admins ohne
Zugriffsrolle behalten zur Abwaertskompatibilitaet Vollzugriff.
Keines der Rechte gibt Zugriff auf Rohantworten -- die existieren im Portal nicht (CLAUDE.md).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access import AccessRole, PersonAccessRole
from app.models.person import Person, Role, RoleAssignment

PERMISSIONS: dict[str, dict[str, str]] = {
    "surveys.manage": {"label": "Umfragen anlegen und bearbeiten", "hint": "Umfrage gestalten, Fragebögen veröffentlichen, Report-Layout und Exporte gestalten"},
    "rounds.manage": {"label": "Befragungsrunden verwalten", "hint": "Runden planen/starten/schließen, Erinnerungen, Code-Briefe, Reports verteilen"},
    "results.view": {"label": "Auswertungen ansehen", "hint": "Rücklauf, Benchmarks, Vergleiche, NPS und Exporte (ohne Rohantworten)"},
    "users.manage": {"label": "Benutzer & Organisation verwalten", "hint": "SAP-Import, Personen, Organigramm"},
    "settings.manage": {"label": "Einstellungen & Rechte verwalten", "hint": "Nachrichtenvorlagen, Zugriffsrollen, Admin-Zuweisung"},
}

DEFAULT_ROLES = [
    ("Vollzugriff", "Alle Verwaltungsfunktionen", list(PERMISSIONS)),
    ("Umfrage & Auswertung", "Umfragen anlegen, Runden führen und alle Werte sehen", ["surveys.manage", "rounds.manage", "results.view"]),
    ("Nur Auswertung", "Alle Werte ansehen, aber nichts verändern", ["results.view"]),
]


def ensure_default_roles(db: Session) -> None:
    existing = {r.name for r in db.execute(select(AccessRole)).scalars()}
    for name, desc, perms in DEFAULT_ROLES:
        if name not in existing:
            db.add(AccessRole(name=name, description=desc, permissions=perms, is_system=True))
    db.commit()


def get_permissions(db: Session, person: Person) -> set[str]:
    is_admin = db.execute(
        select(RoleAssignment.id).where(RoleAssignment.person_id == person.id, RoleAssignment.role == Role.admin)
    ).first()
    if not is_admin:
        return set()
    rows = db.execute(
        select(AccessRole.permissions).join(PersonAccessRole, PersonAccessRole.access_role_id == AccessRole.id)
        .where(PersonAccessRole.person_id == person.id)
    ).scalars().all()
    if not rows:
        return set(PERMISSIONS)  # Legacy-Admin ohne Zugriffsrolle = Vollzugriff
    return {p for perms in rows for p in perms if p in PERMISSIONS}
