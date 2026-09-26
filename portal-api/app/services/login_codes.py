"""Einmalcode-Login fuer Personen ohne E-Mail (CLAUDE.md
'Produktionsmitarbeitende ohne E-Mail'). Codes werden nur gehasht gespeichert."""

from __future__ import annotations

import secrets

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.login_code import LoginCode
from app.models.person import Person

# Ohne 0/O/1/I: verwechslungsgefaehrdete Zeichen vermeiden (Brief wird gedruckt)
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code() -> str:
    return "-".join("".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(2))


def create_login_code(db: Session, person: Person, round_id: int) -> str:
    """Erzeugt einen neuen Klartext-Code, speichert nur dessen Hash und gibt
    den Klartext einmalig zurueck (fuer den Code-Brief)."""
    code = generate_code()
    db.add(LoginCode(person_id=person.id, round_id=round_id, code_hash=bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()))
    db.commit()
    return code


def verify_login_code(db: Session, person: Person, code: str) -> LoginCode | None:
    codes = db.execute(
        select(LoginCode).where(LoginCode.person_id == person.id).order_by(LoginCode.created_at.desc())
    ).scalars().all()
    for entry in codes:
        if bcrypt.checkpw(code.encode(), entry.code_hash.encode()):
            return entry
    return None
