from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.db import get_db
from app.models.notification import MailTemplate, Notification
from app.models.person import Role
from app.schemas.notification import MailTemplateOut, MailTemplateUpdateIn, NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications/mine", response_model=list[NotificationOut])
def my_notifications(
    current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Notification]:
    return db.execute(
        select(Notification)
        .where(Notification.person_id == current_user.person.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
    ).scalars().all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.person_id != current_user.person.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benachrichtigung nicht gefunden")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
    return notification


mail_template_router = APIRouter(
    prefix="/mail-templates", tags=["mail-templates"], dependencies=[Depends(require_permission("settings.manage"))]
)


@mail_template_router.get("", response_model=list[MailTemplateOut])
def list_mail_templates(db: Session = Depends(get_db)) -> list[MailTemplate]:
    return db.execute(select(MailTemplate)).scalars().all()


@mail_template_router.put("/{key}", response_model=MailTemplateOut)
def update_mail_template(key: str, payload: MailTemplateUpdateIn, db: Session = Depends(get_db)) -> MailTemplate:
    template = db.execute(select(MailTemplate).where(MailTemplate.key == key)).scalar_one_or_none()
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden")
    template.subject = payload.subject
    template.body_html = payload.body_html
    db.commit()
    return template
