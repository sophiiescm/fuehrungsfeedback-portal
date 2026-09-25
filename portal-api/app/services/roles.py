"""Automatische Rollenableitung (CLAUDE.md: "fuehrungskraft: wird automatisch
vergeben, wenn die Person >= 1 direkt Unterstellte hat"; "mitarbeiter: alle
Personen"). Die `admin`-Rolle wird nie hier angefasst, sie wird manuell vergeben.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person import Person, Role, RoleAssignment


def recompute_roles(db: Session) -> dict[str, int]:
    persons = db.execute(select(Person)).scalars().all()
    active_by_pnr = {p.personalnummer: p for p in persons if p.aktiv}

    has_active_report: set[str] = set()
    for p in persons:
        if p.aktiv and p.manager_personalnummer and p.manager_personalnummer in active_by_pnr:
            has_active_report.add(p.manager_personalnummer)

    existing_assignments = db.execute(select(RoleAssignment)).scalars().all()
    by_person_and_role: dict[tuple[int, Role], RoleAssignment] = {
        (a.person_id, a.role): a for a in existing_assignments
    }

    granted_mitarbeiter = 0
    granted_fk = 0
    revoked_fk = 0

    for person in persons:
        if not person.aktiv:
            continue
        if (person.id, Role.mitarbeiter) not in by_person_and_role:
            db.add(RoleAssignment(person_id=person.id, role=Role.mitarbeiter))
            granted_mitarbeiter += 1

        should_be_fk = person.personalnummer in has_active_report
        has_fk = (person.id, Role.fuehrungskraft) in by_person_and_role
        if should_be_fk and not has_fk:
            db.add(RoleAssignment(person_id=person.id, role=Role.fuehrungskraft))
            granted_fk += 1
        elif not should_be_fk and has_fk:
            db.delete(by_person_and_role[(person.id, Role.fuehrungskraft)])
            revoked_fk += 1

    db.commit()
    return {
        "mitarbeiter_vergeben": granted_mitarbeiter,
        "fuehrungskraft_vergeben": granted_fk,
        "fuehrungskraft_entzogen": revoked_fk,
    }
