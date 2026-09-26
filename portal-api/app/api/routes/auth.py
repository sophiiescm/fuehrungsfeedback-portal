import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.auth.security import create_access_token
from app.core.config import get_settings
from app.db import get_db
from app.models.person import Person, RoleAssignment
from app.services import sso
from app.services.login_codes import verify_login_code
from app.services.rate_limit import login_limiter

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


class CodeLoginIn(BaseModel):
    personalnummer: str
    code: str


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


@router.post("/code-login", response_model=TokenOut)
def code_login(payload: CodeLoginIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    """Anmeldung mit Personalnummer + Einmalcode fuer Personen ohne E-Mail
    (CLAUDE.md 'Produktionsmitarbeitende ohne E-Mail')."""
    keys = [f"pnr:{payload.personalnummer}", f"ip:{request.client.host if request.client else '?'}"]
    if any(login_limiter.blocked(k) for k in keys):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Fehlversuche. Bitte später erneut versuchen.")
    person = db.execute(
        select(Person).where(Person.personalnummer == payload.personalnummer)
    ).scalar_one_or_none()
    match = verify_login_code(db, person, payload.code) if person is not None and person.aktiv else None
    if match is None:
        for k in keys:
            login_limiter.fail(k)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Personalnummer oder Code ungültig")
    for k in keys:
        login_limiter.reset(k)

    roles = db.execute(select(RoleAssignment.role).where(RoleAssignment.person_id == person.id)).scalars().all()
    token = create_access_token(person.id, [r.value for r in roles])
    return TokenOut(access_token=token)


class AppSsoIn(BaseModel):
    assertion: str


class OidcCallbackIn(BaseModel):
    code: str
    state: str


@router.post("/app-sso", response_model=TokenOut)
def app_sso(payload: AppSsoIn, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    """Trusted-App-SSO: Anmeldung aus der Mitarbeiter-App per signierter Einmal-Assertion."""
    key = f"ip:{request.client.host if request.client else '?'}"
    if login_limiter.blocked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Fehlversuche.")
    try:
        person = sso.verify_app_assertion(db, payload.assertion)
    except sso.SsoError as exc:
        login_limiter.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return TokenOut(access_token=sso.issue_token(db, person))


@router.get("/oidc/login")
def oidc_login() -> dict:
    if not get_settings().oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC ist deaktiviert (OIDC_ENABLED=false)")
    return {"url": sso.oidc_authorization_url()}


@router.post("/oidc/callback", response_model=TokenOut)
def oidc_callback(payload: OidcCallbackIn, db: Session = Depends(get_db)) -> TokenOut:
    if not get_settings().oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC ist deaktiviert (OIDC_ENABLED=false)")
    try:
        person = sso.oidc_complete(db, payload.code, payload.state)
    except (sso.SsoError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"SSO fehlgeschlagen: {exc}") from exc
    return TokenOut(access_token=sso.issue_token(db, person))


@router.get("/methods")
def login_methods() -> dict:
    s = get_settings()
    return {"oidc": s.oidc_enabled, "app_sso": bool(s.app_sso_secret)}
