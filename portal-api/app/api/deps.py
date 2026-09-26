from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db import get_db
from app.models.person import Person, Role

_bearer = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, person: Person, roles: list[Role]):
        self.person = person
        self.roles = roles

    def has_role(self, role: Role) -> bool:
        return role in self.roles


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    person = db.get(Person, int(payload["sub"]))
    if person is None or not person.aktiv:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Person nicht gefunden oder deaktiviert")

    roles = [Role(r) for r in payload.get("roles", [])]
    return CurrentUser(person=person, roles=roles)


def require_role(*allowed_roles: Role):
    def _dependency(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        if not any(current_user.has_role(r) for r in allowed_roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung fuer diese Aktion")
        # Audit-Log fuer Admin-Aktionen (nur schreibende Requests, nie Inhalte/Antworten)
        if Role.admin in allowed_roles and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            from app.models.system import AuditLog

            db.add(AuditLog(
                actor_person_id=current_user.person.id,
                action=f"{request.method} {request.url.path}",
                target_type="http",
                detail={"query": dict(request.query_params)},
            ))
            db.commit()
        return current_user

    return _dependency


def require_permission(*perms: str, view_perms: tuple[str, ...] = (), view_path=None):
    """Admin-Zugang plus mindestens eines der Rechte `perms`. Optional duerfen Inhaber eines der
    `view_perms` reine GET-Abrufe machen (optional nur fuer Pfade, die `view_path(path)` erlaubt)."""

    def _dependency(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        from app.services.permissions import get_permissions

        if Role.admin not in current_user.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung fuer diese Aktion")
        have = get_permissions(db, current_user.person)
        allowed = bool(have & set(perms))
        if not allowed and request.method == "GET" and have & set(view_perms):
            allowed = view_path is None or view_path(request.url.path)
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung fuer diese Aktion")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            from app.models.system import AuditLog

            db.add(AuditLog(
                actor_person_id=current_user.person.id,
                action=f"{request.method} {request.url.path}",
                target_type="http",
                detail={"query": dict(request.query_params)},
            ))
            db.commit()
        return current_user

    return _dependency
