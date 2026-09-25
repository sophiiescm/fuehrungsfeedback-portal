"""Minimale Testnutzer fuer die lokale Entwicklung (Dev-Login).

Das vollstaendige Seed-Skript (1.900 fiktive Personen, siehe CLAUDE.md) folgt
in Phase 2 unter seed/. Phase 1 braucht nur je einen Testnutzer pro Rolle,
damit sich Login und Sidebar pro Rolle manuell pruefen lassen
(Akzeptanzkriterium: 'Login als Admin, FK und MA moeglich').
Wird nur ausgefuehrt, wenn APP_ENV=dev, und ist idempotent (ueberspringt,
sobald bereits Personen existieren).
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models.person import OrgUnit, Person, Role, RoleAssignment


def ensure_dev_fixture_users() -> None:
    db = SessionLocal()
    try:
        if db.execute(select(Person).limit(1)).scalar_one_or_none() is not None:
            return

        org_unit = OrgUnit(name="Dev-Testabteilung", fachbereich="Dev-Fachbereich")
        db.add(org_unit)
        db.flush()

        admin = Person(
            personalnummer="DEV-ADMIN",
            vorname="Anna",
            nachname="Admin",
            email="anna.admin@example.test",
            org_unit_id=org_unit.id,
            manager_personalnummer=None,
        )
        leader = Person(
            personalnummer="DEV-FK",
            vorname="Frank",
            nachname="Fuehrungskraft",
            email="frank.fk@example.test",
            org_unit_id=org_unit.id,
            manager_personalnummer="DEV-ADMIN",
        )
        employee = Person(
            personalnummer="DEV-MA",
            vorname="Mia",
            nachname="Mitarbeiterin",
            email="mia.ma@example.test",
            org_unit_id=org_unit.id,
            manager_personalnummer="DEV-FK",
        )
        db.add_all([admin, leader, employee])
        db.flush()

        db.add_all(
            [
                RoleAssignment(person_id=admin.id, role=Role.admin),
                RoleAssignment(person_id=leader.id, role=Role.fuehrungskraft),
                RoleAssignment(person_id=employee.id, role=Role.mitarbeiter),
            ]
        )
        db.commit()
    finally:
        db.close()
