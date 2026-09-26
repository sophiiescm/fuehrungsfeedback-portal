"""In-Portal-Benachrichtigungen fuer alle, zusaetzlich E-Mail wenn vorhanden
(CLAUDE.md 'Benachrichtigungen')."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import MailTemplate, Notification
from app.models.person import Person
from app.services.mail import render, send_mail


def notify(db: Session, person: Person, type_: str, title: str, body: str, round_id: int | None = None) -> None:
    db.add(Notification(person_id=person.id, round_id=round_id, type=type_, title=title, body=body))
    if person.email:
        send_mail(person.email, title, body)
    db.commit()


def notify_from_template(
    db: Session, person: Person, template_key: str, context: dict, round_id: int | None = None
) -> bool:
    """Rendert eine `mail_template`-Zeile und verschickt sie. Gibt False zurueck
    (ohne Fehler), wenn keine Vorlage mit diesem Schluessel existiert."""
    template = db.execute(select(MailTemplate).where(MailTemplate.key == template_key)).scalar_one_or_none()
    if template is None:
        return False
    subject = render(template.subject, **context)
    body = render(template.body_html, **context)
    notify(db, person, template_key, subject, body, round_id=round_id)
    return True
