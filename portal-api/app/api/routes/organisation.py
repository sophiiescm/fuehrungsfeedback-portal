from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import get_settings
from app.db import get_db
from app.models.person import OrgUnit, Person, Role, RoleAssignment
from app.models.system import ImportLog
from app.schemas.organisation import (
    ChangedPersonOut,
    FieldChangeOut,
    ImportDiffOut,
    ImportLogOut,
    ImportScheduleIn,
    ImportScheduleOut,
    NewPersonOut,
    OrgPathEntryOut,
    OrgTreeNodeOut,
    PersonDetailOut,
    PersonListItemOut,
    PersonListOut,
    SetAdminRoleIn,
)
from app.services.org_import import ImportDiff, dry_run_import
from app.services.org_import import apply_import as apply_org_import
from app.services.org_source import CsvOrgSource, OrgSourceError
from app.services.roles import recompute_roles
from app.services.scheduler import get_schedule_config, set_schedule_config

router = APIRouter(prefix="/organisation", tags=["organisation"], dependencies=[Depends(require_role(Role.admin))])


def _diff_to_schema(diff: ImportDiff) -> ImportDiffOut:
    return ImportDiffOut(
        new=[
            NewPersonOut(
                personalnummer=r.personalnummer,
                vorname=r.vorname,
                nachname=r.nachname,
                org_einheit=r.org_einheit,
                fachbereich=r.fachbereich,
            )
            for r in diff.new
        ],
        changed=[
            ChangedPersonOut(
                personalnummer=c.personalnummer,
                changes=[FieldChangeOut(field=fc.field, old=fc.old, new=fc.new) for fc in c.changes],
            )
            for c in diff.changed
        ],
        deactivated=diff.deactivated,
        unchanged_count=diff.unchanged_count,
        issues=diff.issues,
    )


async def _read_csv_source(file: UploadFile) -> CsvOrgSource:
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV muss UTF-8-kodiert sein") from exc
    return CsvOrgSource(content)


@router.post("/import/dry-run", response_model=ImportDiffOut)
async def import_dry_run(file: UploadFile, db: Session = Depends(get_db)) -> ImportDiffOut:
    source = await _read_csv_source(file)
    try:
        records = source.fetch()
    except OrgSourceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    diff = dry_run_import(db, records, triggered_by="admin-ui")
    return _diff_to_schema(diff)


@router.post("/import/apply", response_model=ImportDiffOut)
async def import_apply(file: UploadFile, db: Session = Depends(get_db)) -> ImportDiffOut:
    source = await _read_csv_source(file)
    try:
        records = source.fetch()
    except OrgSourceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    diff = apply_org_import(db, records, triggered_by="admin-ui")
    recompute_roles(db)
    return _diff_to_schema(diff)


@router.get("/import/logs", response_model=list[ImportLogOut])
def import_logs(db: Session = Depends(get_db)) -> list[ImportLog]:
    return (
        db.execute(select(ImportLog).order_by(ImportLog.started_at.desc()).limit(50)).scalars().all()
    )


def _team_size(db: Session, personalnummer: str) -> int:
    reports = db.execute(
        select(Person).where(Person.manager_personalnummer == personalnummer, Person.aktiv.is_(True))
    ).scalars().all()
    return len(reports)


def _person_roles(db: Session, person_id: int) -> list[str]:
    roles = db.execute(select(RoleAssignment.role).where(RoleAssignment.person_id == person_id)).scalars().all()
    return [r.value for r in roles]


@router.get("/persons", response_model=PersonListOut)
def list_persons(
    q: str | None = Query(None, description="Suche in Name oder Personalnummer"),
    fachbereich: str | None = None,
    role: Role | None = None,
    has_email: bool | None = None,
    only_active: bool = True,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> PersonListOut:
    stmt = select(Person)
    if only_active:
        stmt = stmt.where(Person.aktiv.is_(True))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (Person.personalnummer.ilike(like))
            | (Person.vorname.ilike(like))
            | (Person.nachname.ilike(like))
        )
    if fachbereich:
        stmt = stmt.join(OrgUnit).where(OrgUnit.fachbereich == fachbereich)
    if has_email is not None:
        stmt = stmt.where(Person.email.is_not(None) if has_email else Person.email.is_(None))

    all_matching = db.execute(stmt).scalars().unique().all()

    items: list[PersonListItemOut] = []
    for p in all_matching:
        roles = _person_roles(db, p.id)
        if role is not None and role.value not in roles:
            continue
        items.append(
            PersonListItemOut(
                id=p.id,
                personalnummer=p.personalnummer,
                full_name=p.full_name,
                email=p.email,
                fachbereich=p.org_unit.fachbereich if p.org_unit else None,
                org_einheit=p.org_unit.name if p.org_unit else None,
                roles=roles,
                aktiv=p.aktiv,
            )
        )

    total = len(items)
    return PersonListOut(items=items[offset : offset + limit], total=total)


@router.get("/persons/{person_id}", response_model=PersonDetailOut)
def get_person(person_id: int, db: Session = Depends(get_db)) -> PersonDetailOut:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")

    by_pnr = {p.personalnummer: p for p in db.execute(select(Person)).scalars().all()}
    path: list[OrgPathEntryOut] = []
    current = person
    visited: set[str] = set()
    while current.manager_personalnummer and current.manager_personalnummer not in visited:
        visited.add(current.manager_personalnummer)
        manager = by_pnr.get(current.manager_personalnummer)
        if manager is None:
            break
        path.append(OrgPathEntryOut(personalnummer=manager.personalnummer, full_name=manager.full_name))
        current = manager

    return PersonDetailOut(
        id=person.id,
        personalnummer=person.personalnummer,
        vorname=person.vorname,
        nachname=person.nachname,
        email=person.email,
        fachbereich=person.org_unit.fachbereich if person.org_unit else None,
        org_einheit=person.org_unit.name if person.org_unit else None,
        standort=person.standort,
        aktiv=person.aktiv,
        roles=_person_roles(db, person.id),
        team_size=_team_size(db, person.personalnummer),
        org_path=list(reversed(path)),
    )


@router.post("/persons/{person_id}/admin-role", response_model=PersonDetailOut)
def set_admin_role(person_id: int, payload: SetAdminRoleIn, db: Session = Depends(get_db)) -> PersonDetailOut:
    """Admin-Rolle wird ausschliesslich manuell vergeben (CLAUDE.md), im
    Gegensatz zu fuehrungskraft/mitarbeiter, die automatisch abgeleitet werden."""
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")

    existing = db.execute(
        select(RoleAssignment).where(RoleAssignment.person_id == person_id, RoleAssignment.role == Role.admin)
    ).scalar_one_or_none()

    if payload.is_admin and existing is None:
        db.add(RoleAssignment(person_id=person_id, role=Role.admin))
    elif not payload.is_admin and existing is not None:
        db.delete(existing)
    db.commit()

    return get_person(person_id, db)


@router.post("/persons/{person_id}/deactivate", response_model=PersonDetailOut)
def deactivate_person(person_id: int, db: Session = Depends(get_db)) -> PersonDetailOut:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")
    person.aktiv = False
    db.commit()
    recompute_roles(db)
    return get_person(person_id, db)


@router.get("/import/schedule", response_model=ImportScheduleOut)
def get_import_schedule(db: Session = Depends(get_db)) -> ImportScheduleOut:
    return ImportScheduleOut(**get_schedule_config(db))


@router.put("/import/schedule", response_model=ImportScheduleOut)
def put_import_schedule(payload: ImportScheduleIn, db: Session = Depends(get_db)) -> ImportScheduleOut:
    config = set_schedule_config(db, payload.model_dump())
    return ImportScheduleOut(**config)


@router.get("/fachbereiche", response_model=list[str])
def list_fachbereiche(db: Session = Depends(get_db)) -> list[str]:
    values = db.execute(select(OrgUnit.fachbereich).distinct()).scalars().all()
    return sorted(values)


def _build_tree_node(person: Person, by_manager: dict[str, list[Person]], settings_threshold: int) -> OrgTreeNodeOut:
    reports = by_manager.get(person.personalnummer, [])
    return OrgTreeNodeOut(
        personalnummer=person.personalnummer,
        full_name=person.full_name,
        fachbereich=person.org_unit.fachbereich if person.org_unit else None,
        team_size=len(reports),
        team_too_small=0 < len(reports) < settings_threshold,
        children=[_build_tree_node(child, by_manager, settings_threshold) for child in reports],
    )


@router.get("/tree", response_model=list[OrgTreeNodeOut])
def get_org_tree(db: Session = Depends(get_db)) -> list[OrgTreeNodeOut]:
    settings = get_settings()
    persons = db.execute(select(Person).where(Person.aktiv.is_(True))).scalars().all()
    by_pnr = {p.personalnummer: p for p in persons}

    by_manager: dict[str, list[Person]] = {}
    roots: list[Person] = []
    for p in persons:
        if p.manager_personalnummer and p.manager_personalnummer in by_pnr:
            by_manager.setdefault(p.manager_personalnummer, []).append(p)
        else:
            roots.append(p)

    return [_build_tree_node(r, by_manager, settings.min_team_size_for_invitation) for r in roots]
