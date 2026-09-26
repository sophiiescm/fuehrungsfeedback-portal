"""Code-Briefe (mit QR) und Team-Aushang fuer Personen ohne E-Mail.

Der Aushang enthaelt bewusst KEINEN Teilnahmestatus einzelner Personen
(CLAUDE.md 'Benachrichtigungen'). weasyprint wird nur lazy importiert
(docs/ENTSCHEIDUNGEN.md Nr. 21).
"""

from __future__ import annotations

import base64
import io

import qrcode
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.person import Person
from app.models.round import Participation, Round, RoundTarget
from app.services.login_codes import create_login_code

LETTER_HTML = Template(
    """<html><head><meta charset="utf-8"><style>
    body{font-family:'DejaVu Sans',sans-serif;font-size:12pt}
    .letter{page-break-after:always;padding:30px}
    .code{font-size:22pt;letter-spacing:3px;font-weight:bold;margin:16px 0}
    </style></head><body>
    {% for l in letters %}<div class="letter">
    <h2>{{ round_name }}</h2>
    <p>Guten Tag {{ l.name }},</p>
    <p>Sie sind zu einer anonymen Befragung eingeladen (bis {{ end_date }}).</p>
    <p>Anmeldung mit Personalnummer <strong>{{ l.personalnummer }}</strong> und Einmalcode:</p>
    <div class="code">{{ l.code }}</div>
    <p>Adresse: {{ portal_url }}</p>
    <img src="data:image/png;base64,{{ l.qr }}" width="140">
    </div>{% endfor %}</body></html>"""
)

NOTICE_HTML = Template(
    """<html><head><meta charset="utf-8"><style>body{font-family:'DejaVu Sans',sans-serif}
    .page{page-break-after:always;padding:30px}</style></head><body>
    {% for n in notices %}<div class="page"><h1>Befragung: {{ round_name }}</h1>
    <h2>Team {{ n.leader }}</h2>
    <p>Teilnahme bis {{ end_date }} unter {{ portal_url }}.
    Personen ohne E-Mail erhalten ihren Zugangscode als persoenlichen Brief.
    Die Teilnahme ist anonym.</p>
    <p>Teamgroesse: {{ n.team_size }}</p></div>{% endfor %}</body></html>"""
)


def _qr_base64(text: str) -> str:
    buf = io.BytesIO()
    qrcode.make(text).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def build_letters_html(db: Session, round_: Round) -> str:
    portal_url = get_settings().portal_public_url
    rows = db.execute(
        select(Person)
        .join(Participation, Participation.person_id == Person.id)
        .where(Participation.round_id == round_.id, Person.email.is_(None))
        .distinct()
    ).scalars().all()
    letters = [
        {
            "name": p.full_name,
            "personalnummer": p.personalnummer,
            "code": (code := create_login_code(db, p, round_.id)),
            "qr": _qr_base64(f"{portal_url}/login?pnr={p.personalnummer}"),
        }
        for p in rows
    ]
    return LETTER_HTML.render(letters=letters, round_name=round_.name,
                              end_date=round_.end_at.date().isoformat(), portal_url=portal_url)


def build_notices_html(db: Session, round_: Round) -> str:
    portal_url = get_settings().portal_public_url
    notices = []
    for t in db.execute(select(RoundTarget).where(RoundTarget.round_id == round_.id, RoundTarget.evaluable.is_(True))).scalars():
        has_no_email = db.execute(
            select(Person.id)
            .join(Participation, Participation.person_id == Person.id)
            .where(Participation.round_target_id == t.id, Person.email.is_(None))
            .limit(1)
        ).first()
        if has_no_email:
            notices.append({"leader": t.leader.full_name, "team_size": t.team_size_snapshot})
    return NOTICE_HTML.render(notices=notices, round_name=round_.name,
                              end_date=round_.end_at.date().isoformat(), portal_url=portal_url)


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # lazy, siehe ENTSCHEIDUNGEN Nr. 21

    return HTML(string=html).write_pdf()
