"""Datenminimierung / Loeschfristen (DSGVO). Laeuft taeglich per Scheduler.

- Rohantworten: Die pro Fuehrungskraft angelegten LimeSurvey-Umfragen (mit allen Einzelantworten)
  werden `retention_survey_days` nach Abschluss der Runde (Status 'berichtet') geloescht. Das Portal
  behaelt nur Aggregate und den geschwaerzten Report.
- Benachrichtigungen, Login-Codes, Audit-Log und eingeloeste SSO-Assertions werden nach ihren Fristen entfernt.
Fristen per ENV (RETENTION_*_DAYS), siehe docs/DATENSCHUTZ-KONZEPT.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.login_code import LoginCode
from app.models.notification import Notification
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.sso import UsedAssertion
from app.models.system import AuditLog
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError

logger = logging.getLogger(__name__)


def run_retention(db: Session, now: datetime | None = None, client_factory=LimeSurveyClient) -> dict:
    s = get_settings()
    now = now or datetime.now(timezone.utc)
    result = {"surveys_deleted": 0, "notifications": 0, "login_codes": 0, "audit": 0, "assertions": 0}

    # 1) LimeSurvey-Rohantworten
    cutoff = now - timedelta(days=s.retention_survey_days)
    targets = db.execute(
        select(RoundTarget).join(Round, Round.id == RoundTarget.round_id)
        .where(Round.status == RoundStatus.berichtet, Round.end_at < cutoff, RoundTarget.limesurvey_sid.is_not(None))
    ).scalars().all()
    if targets:
        client = client_factory()
        try:
            for t in targets:
                try:
                    client.delete_survey(t.limesurvey_sid)
                except LimeSurveyError:
                    logger.warning("LimeSurvey-Umfrage %s nicht loeschbar (evtl. schon weg)", t.limesurvey_sid)
                t.limesurvey_sid = None
                result["surveys_deleted"] += 1
        finally:
            client.close()
        db.commit()

    # 2) Portal-Daten mit Frist
    def purge(model, column, days, key):
        res = db.execute(delete(model).where(column < now - timedelta(days=days)))
        result[key] = res.rowcount or 0

    purge(Notification, Notification.created_at, s.retention_notification_days, "notifications")
    purge(LoginCode, LoginCode.created_at, s.retention_login_code_days, "login_codes")
    purge(AuditLog, AuditLog.created_at, s.retention_audit_days, "audit")
    purge(UsedAssertion, UsedAssertion.expires_at, 1, "assertions")
    db.commit()
    return result
