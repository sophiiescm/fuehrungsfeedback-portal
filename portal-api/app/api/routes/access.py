"""Zugriffsrollen und Admin-Zuweisung (Einstellungen -> Nutzer & Rechte)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db import get_db
from app.models.access import AccessRole, PersonAccessRole
from app.models.person import Person, Role, RoleAssignment
from app.services.permissions import PERMISSIONS, ensure_default_roles, get_permissions

router = APIRouter(prefix="/access", tags=["access"], dependencies=[Depends(require_permission("settings.manage"))])


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(None, max_length=300)
    permissions: list[str]


class AssignIn(BaseModel):
    role_ids: list[int]


def _role_out(db: Session, r: AccessRole) -> dict:
    members = db.execute(select(func.count()).select_from(PersonAccessRole).where(PersonAccessRole.access_role_id == r.id)).scalar_one()
    return {"id": r.id, "name": r.name, "description": r.description, "permissions": r.permissions, "is_system": r.is_system, "members": members}


def _validate(perms: list[str]) -> list[str]:
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannte Rechte: {', '.join(unknown)}")
    return [p for p in PERMISSIONS if p in perms]  # feste Reihenfolge, ohne Duplikate


def _settings_admins(db: Session) -> int:
    """Anzahl Personen, die Einstellungen/Rechte verwalten duerfen (Aussperr-Schutz)."""
    admins = db.execute(select(Person).join(RoleAssignment, RoleAssignment.person_id == Person.id)
                        .where(RoleAssignment.role == Role.admin, Person.aktiv.is_(True))).scalars().all()
    return sum(1 for p in admins if "settings.manage" in get_permissions(db, p))


@router.get("/permissions")
def list_permissions() -> list[dict]:
    return [{"key": k, **v} for k, v in PERMISSIONS.items()]


@router.get("/roles")
def list_roles(db: Session = Depends(get_db)) -> list[dict]:
    ensure_default_roles(db)
    return [_role_out(db, r) for r in db.execute(select(AccessRole).order_by(AccessRole.id)).scalars()]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleIn, db: Session = Depends(get_db)) -> dict:
    if db.execute(select(AccessRole).where(AccessRole.name == payload.name.strip())).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Eine Rolle mit diesem Namen existiert bereits")
    r = AccessRole(name=payload.name.strip(), description=payload.description, permissions=_validate(payload.permissions))
    db.add(r)
    db.commit()
    return _role_out(db, r)


@router.put("/roles/{role_id}")
def update_role(role_id: int, payload: RoleIn, db: Session = Depends(get_db)) -> dict:
    r = db.get(AccessRole, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rolle nicht gefunden")
    old = r.permissions
    r.name, r.description, r.permissions = payload.name.strip(), payload.description, _validate(payload.permissions)
    db.flush()
    if "settings.manage" in old and _settings_admins(db) < 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Mindestens eine Person muss Einstellungen & Rechte verwalten dürfen")
    db.commit()
    return _role_out(db, r)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: Session = Depends(get_db)) -> None:
    r = db.get(AccessRole, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rolle nicht gefunden")
    if r.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vordefinierte Rollen können nicht gelöscht werden")
    holders = db.execute(select(PersonAccessRole.person_id).where(PersonAccessRole.access_role_id == role_id)).scalars().all()
    db.query(PersonAccessRole).filter(PersonAccessRole.access_role_id == role_id).delete()
    db.delete(r)
    db.flush()
    # Wer danach keine Zugriffsrolle mehr hat, verliert den Admin-Zugang (sonst Vollzugriff durch Legacy-Regel)
    for pid in holders:
        if not db.execute(select(PersonAccessRole).where(PersonAccessRole.person_id == pid)).first():
            db.query(RoleAssignment).filter(RoleAssignment.person_id == pid, RoleAssignment.role == Role.admin).delete()
    db.flush()
    if _settings_admins(db) < 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Mindestens eine Person muss Einstellungen & Rechte verwalten dürfen")
    db.commit()


@router.get("/admins")
def list_admins(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Person).join(RoleAssignment, RoleAssignment.person_id == Person.id)
                      .where(RoleAssignment.role == Role.admin).order_by(Person.nachname, Person.vorname)).scalars().all()
    out = []
    for p in rows:
        ids = db.execute(select(PersonAccessRole.access_role_id).where(PersonAccessRole.person_id == p.id)).scalars().all()
        out.append({"person_id": p.id, "personalnummer": p.personalnummer, "full_name": p.full_name, "aktiv": p.aktiv,
                    "role_ids": list(ids), "permissions": sorted(get_permissions(db, p))})
    return out


@router.get("/persons/search")
def search_persons(q: str, db: Session = Depends(get_db)) -> list[dict]:
    like = f"%{q.strip()}%"
    rows = db.execute(select(Person).where(Person.aktiv.is_(True), or_(
        Person.nachname.ilike(like), Person.vorname.ilike(like), Person.personalnummer.ilike(like))).limit(15)).scalars().all()
    return [{"person_id": p.id, "personalnummer": p.personalnummer, "full_name": p.full_name} for p in rows]


@router.put("/persons/{person_id}")
def assign_roles(person_id: int, payload: AssignIn, db: Session = Depends(get_db)) -> dict:
    """Setzt die Zugriffsrollen einer Person. Leere Liste = Admin-Zugang entziehen."""
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")
    ids = set(payload.role_ids)
    if ids and db.execute(select(func.count()).select_from(AccessRole).where(AccessRole.id.in_(ids))).scalar_one() != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Rolle")
    db.query(PersonAccessRole).filter(PersonAccessRole.person_id == person_id).delete()
    for rid in ids:
        db.add(PersonAccessRole(person_id=person_id, access_role_id=rid))
    has_admin = db.execute(select(RoleAssignment).where(RoleAssignment.person_id == person_id, RoleAssignment.role == Role.admin)).scalar_one_or_none()
    if ids and not has_admin:
        db.add(RoleAssignment(person_id=person_id, role=Role.admin))
    elif not ids and has_admin:
        db.delete(has_admin)
    db.flush()
    if _settings_admins(db) < 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Mindestens eine Person muss Einstellungen & Rechte verwalten dürfen")
    db.commit()
    return {"person_id": person_id, "role_ids": sorted(ids), "permissions": sorted(get_permissions(db, person))}
