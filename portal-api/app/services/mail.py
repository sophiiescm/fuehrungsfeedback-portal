"""E-Mail-Versand per SMTP (lokal Mailpit) mit editierbaren Jinja2-Vorlagen
(CLAUDE.md: 'Die Vorlagen sind im Portal bearbeitbar')."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from jinja2 import Template

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def render(template_body: str, **context: object) -> str:
    return Template(template_body).render(**context)


def send_mail(to_email: str, subject: str, html_body: str) -> bool:
    """Gibt False statt zu werfen zurueck, wenn der Versand fehlschlaegt --
    ein SMTP-Ausfall darf eine Runde nie blockieren (die In-Portal-
    Benachrichtigung existiert unabhaengig davon bereits)."""
    settings = get_settings()
    try:
        msg = MIMEText(html_body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("E-Mail-Versand an %s fehlgeschlagen", to_email)
        return False
