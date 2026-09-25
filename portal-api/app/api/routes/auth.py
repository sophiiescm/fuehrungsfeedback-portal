from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.auth.security import create_access_token
from app.core.config import get_settings
from app.db import get_db
from app.models.person import Person, RoleAssignment

router = APIRouter(prefix="/auth", tags=["auth"])


class DevUserOut(BaseModel):
    personalnummer: str
    full_name: str
    roles: list[str]


class DevLoginIn(BaseModel):
    personalnummer: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    personalnummer: str
    full_name: str
    email: str | None
    roles: list[str]


def _require_dev_env() -> None:
    settings = get_settings()
    if settings.app_env != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht verfuegbar")


@router.get("/dev-login/users", response_model=list[DevUserOut])
def list_dev_users(db: Session = Depends(get_db)) -> list[DevUserOut]:
    """Nur aktiv wenn APP_ENV=dev (CLAUDE.md: 'Dev-Login, nur aktiv wenn APP_ENV=dev')."""
    _require_dev_env()
    persons = db.execute(select(Person).where(Person.aktiv.is_(True)).limit(50)).scalars().all()
    result = []
    for p in persons:
        roles = db.execute(
            select(RoleAssignment.role).where(RoleAssignment.person_id == p.id)
        ).scalars().all()
        result.append(DevUserOut(personalnummer=p.personalnummer, full_name=p.full_name, roles=[r.value for r in roles]))
    return result


@router.post("/dev-login", response_model=TokenOut)
def dev_login(payload: DevLoginIn, db: Session = Depends(get_db)) -> TokenOut:
    _require_dev_env()
    person = db.execute(
        select(Person).where(Person.personalnummer == payload.personalnummer)
    ).scalar_one_or_none()
    if person is None or not person.aktiv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")

    roles = db.execute(select(RoleAssignment.role).where(RoleAssignment.person_id == person.id)).scalars().all()
    token = create_access_token(person.id, [r.value for r in roles])
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(current_user: CurrentUser = Depends(get_current_user)) -> MeOut:
    return MeOut(
        personalnummer=current_user.person.personalnummer,
        full_name=current_user.person.full_name,
        email=current_user.person.email,
        roles=[r.value for r in current_user.roles],
    )


@router.get("/oidc/login")
def oidc_login() -> dict:
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC ist deaktiviert (OIDC_ENABLED=false)")
    # Vollstaendiger Redirect-Flow (State-Handling, Callback) wird verdrahtet, sobald
    # ein echter Identity-Provider zum Testen verfuegbar ist (siehe OPEN_QUESTIONS.md).
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "OIDC-Redirect-Flow folgt mit echtem IdP-Test")
