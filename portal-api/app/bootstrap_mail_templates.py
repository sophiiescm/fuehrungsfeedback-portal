"""Standard-E-Mail-Vorlagen (CLAUDE.md: 'Einladung, Erinnerung,
Faelligkeitshinweis, Report verfuegbar'). Im Portal bearbeitbar
(mail_template-Tabelle), hier nur als sinnvoller Ausgangspunkt angelegt.
Idempotent: ueberspringt bereits vorhandene Schluessel."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models.notification import MailTemplate

DEFAULT_TEMPLATES = {
    "invitation": {
        "subject": "Ihre Teilnahme an der Befragungsrunde \"{{ round_name }}\"",
        "body_html": (
            "<p>Sie sind eingeladen, an der Befragungsrunde <strong>{{ round_name }}</strong> "
            "teilzunehmen.</p>"
            "<p>Bitte geben Sie Ihr Feedback bis zum <strong>{{ end_date }}</strong> ab.</p>"
            "{% if feedback_link %}<p><a href=\"{{ feedback_link }}\">Jetzt Feedback geben</a></p>{% endif %}"
            "<p>Ihre Antworten werden anonym erfasst.</p>"
        ),
    },
    "reminder": {
        "subject": "Erinnerung: Ihr Feedback zu \"{{ round_name }}\" fehlt noch",
        "body_html": (
            "<p>Noch {{ days_left }} Tag(e) bis zum Ende der Befragungsrunde "
            "<strong>{{ round_name }}</strong> (bis {{ end_date }}).</p>"
            "{% if feedback_link %}<p><a href=\"{{ feedback_link }}\">Jetzt Feedback geben</a></p>{% endif %}"
        ),
    },
    "due": {
        "subject": "Letzte Gelegenheit: \"{{ round_name }}\" endet heute",
        "body_html": (
            "<p>Die Befragungsrunde <strong>{{ round_name }}</strong> endet heute.</p>"
            "{% if feedback_link %}<p><a href=\"{{ feedback_link }}\">Jetzt Feedback geben</a></p>{% endif %}"
        ),
    },
    "report_ready": {
        "subject": "Ihr Report zu \"{{ round_name }}\" ist verfügbar",
        "body_html": (
            "<p>Der Report für die Befragungsrunde <strong>{{ round_name }}</strong> steht "
            "jetzt im Portal für Sie bereit.</p>"
        ),
    },
}


def ensure_default_mail_templates() -> None:
    db = SessionLocal()
    try:
        existing_keys = set(db.execute(select(MailTemplate.key)).scalars().all())
        for key, content in DEFAULT_TEMPLATES.items():
            if key in existing_keys:
                continue
            db.add(MailTemplate(key=key, subject=content["subject"], body_html=content["body_html"]))
        db.commit()
    finally:
        db.close()
