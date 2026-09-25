"""Orchestriert den SAP-Org-Import: Trockenlauf mit Diff, Plausibilitaetspruefung,
Uebernahme, Protokoll (CLAUDE.md "SAP-Schnittstelle" / TASKS.md Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person import OrgUnit, Person
from app.models.system import ImportLog
from app.services.org_source import OrgRecord, OrgSource

TRACKED_FIELDS = ["vorname", "nachname", "email", "org_einheit", "fachbereich", "standort", "aktiv"]


@dataclass
class FieldChange:
    field: str
    old: object
    new: object


@dataclass
class ChangedPerson:
    personalnummer: str
    changes: list[FieldChange]


@dataclass
class ImportDiff:
    new: list[OrgRecord] = field(default_factory=list)
    changed: list[ChangedPerson] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)
    unchanged_count: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "new": len(self.new),
            "changed": len(self.changed),
            "deactivated": len(self.deactivated),
            "unchanged": self.unchanged_count,
            "issues": list(self.issues),
        }


def check_plausibility(records: list[OrgRecord]) -> list[str]:
    issues: list[str] = []

    seen: set[str] = set()
    duplicates: set[str] = set()
    for r in records:
        if r.personalnummer in seen:
            duplicates.add(r.personalnummer)
        seen.add(r.personalnummer)
    for pnr in sorted(duplicates):
        issues.append(f"Doppelte Personalnummer im Import: {pnr}")

    by_pnr = {r.personalnummer: r for r in records}
    for r in records:
        if r.manager_personalnummer and r.manager_personalnummer not in by_pnr:
            issues.append(
                f"{r.personalnummer}: Vorgesetzte/r {r.manager_personalnummer} fehlt im Import "
                "(evtl. bereits ausgeschieden oder Tippfehler)"
            )

    # Zyklenerkennung ueber die Manager-Kette (nur innerhalb des Imports aufloesbar)
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {r.personalnummer: WHITE for r in records}
    cyclic: set[str] = set()

    def visit(pnr: str, path: list[str]) -> None:
        color[pnr] = GRAY
        manager = by_pnr[pnr].manager_personalnummer
        if manager and manager in by_pnr:
            if color.get(manager) == GRAY:
                cyclic.update(path + [manager])
            elif color.get(manager, WHITE) == WHITE:
                visit(manager, path + [manager])
        color[pnr] = BLACK

    for r in records:
        if color[r.personalnummer] == WHITE:
            visit(r.personalnummer, [r.personalnummer])
    for pnr in sorted(cyclic):
        issues.append(f"Zyklus in der Vorgesetzten-Kette beteiligt: {pnr}")

    return issues


def compute_diff(db: Session, records: list[OrgRecord]) -> ImportDiff:
    diff = ImportDiff()
    diff.issues = check_plausibility(records)

    existing = {p.personalnummer: p for p in db.execute(select(Person)).scalars().all()}
    incoming_pnrs = {r.personalnummer for r in records}

    for record in records:
        person = existing.get(record.personalnummer)
        if person is None:
            diff.new.append(record)
            continue

        changes: list[FieldChange] = []
        current_fachbereich = person.org_unit.fachbereich if person.org_unit else None
        current_org_einheit = person.org_unit.name if person.org_unit else None
        comparable = {
            "vorname": (person.vorname, record.vorname),
            "nachname": (person.nachname, record.nachname),
            "email": (person.email, record.email),
            "org_einheit": (current_org_einheit, record.org_einheit),
            "fachbereich": (current_fachbereich, record.fachbereich),
            "standort": (person.standort, record.standort),
            "aktiv": (person.aktiv, record.aktiv),
        }
        for f, (old, new) in comparable.items():
            if old != new:
                changes.append(FieldChange(field=f, old=old, new=new))
        if person.manager_personalnummer != record.manager_personalnummer:
            changes.append(
                FieldChange(
                    field="manager_personalnummer",
                    old=person.manager_personalnummer,
                    new=record.manager_personalnummer,
                )
            )

        if changes:
            diff.changed.append(ChangedPerson(personalnummer=record.personalnummer, changes=changes))
        else:
            diff.unchanged_count += 1

    for pnr, person in existing.items():
        if pnr not in incoming_pnrs and person.aktiv:
            diff.deactivated.append(pnr)

    return diff


def _get_or_create_org_unit(db: Session, cache: dict[str, OrgUnit], name: str, fachbereich: str) -> OrgUnit:
    unit = cache.get(name)
    if unit is None:
        unit = db.execute(select(OrgUnit).where(OrgUnit.name == name)).scalar_one_or_none()
        if unit is None:
            unit = OrgUnit(name=name, fachbereich=fachbereich)
            db.add(unit)
            db.flush()
        cache[name] = unit
    if unit.fachbereich != fachbereich:
        unit.fachbereich = fachbereich
    return unit


def apply_import(db: Session, records: list[OrgRecord], triggered_by: str) -> ImportDiff:
    """Uebernimmt den Importstand in die Datenbank. Rollenableitung erfolgt separat
    (siehe app.services.roles.recompute_fuehrungskraft_roles), damit ein Trockenlauf
    diesen Schritt nicht beruehrt."""
    diff = compute_diff(db, records)

    org_unit_cache: dict[str, OrgUnit] = {}
    existing = {p.personalnummer: p for p in db.execute(select(Person)).scalars().all()}
    incoming_pnrs = {r.personalnummer for r in records}

    for record in records:
        org_unit = _get_or_create_org_unit(db, org_unit_cache, record.org_einheit, record.fachbereich)
        person = existing.get(record.personalnummer)
        if person is None:
            person = Person(personalnummer=record.personalnummer)
            db.add(person)
            existing[record.personalnummer] = person

        person.vorname = record.vorname
        person.nachname = record.nachname
        person.email = record.email
        person.org_unit_id = org_unit.id
        person.manager_personalnummer = record.manager_personalnummer
        person.standort = record.standort
        person.aktiv = record.aktiv

    for pnr in diff.deactivated:
        existing[pnr].aktiv = False

    db.flush()

    log = ImportLog(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        dry_run=False,
        status="ok",
        triggered_by=triggered_by,
        summary=diff.summary,
    )
    db.add(log)
    db.commit()
    return diff


def dry_run_import(db: Session, records: list[OrgRecord], triggered_by: str) -> ImportDiff:
    diff = compute_diff(db, records)
    log = ImportLog(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        dry_run=True,
        status="ok",
        triggered_by=triggered_by,
        summary=diff.summary,
    )
    db.add(log)
    db.commit()
    return diff


def run_import(source: OrgSource, db: Session, triggered_by: str, dry_run: bool) -> ImportDiff:
    records = source.fetch()
    if dry_run:
        return dry_run_import(db, records, triggered_by)
    return apply_import(db, records, triggered_by)
