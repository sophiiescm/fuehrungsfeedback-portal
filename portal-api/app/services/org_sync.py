"""Organisationsdaten (Teams) aus der konfigurierten SAP-Quelle aktualisieren.

Wird vom naechtlichen Import, beim Start jeder Runde (automatisch/manuell) und ueber den
Button „Jetzt aus SAP aktualisieren“ im Runden-Assistenten genutzt. Ohne konfigurierte
Quelle passiert nichts (dann gilt der zuletzt importierte Stand)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system import ImportLog
from app.services.org_import import apply_import
from app.services.org_source import CsvOrgSource, ODataOrgSource, OrgRecord
from app.services.roles import recompute_roles

logger = logging.getLogger(__name__)


def configured_source(config: dict):
    """OrgSource passend zur Konfiguration oder None."""
    if not config.get("enabled"):
        return None
    if config.get("source") == "odata":
        s = get_settings()
        return ODataOrgSource(s.odata_base_url, s.odata_user, s.odata_password) if s.odata_base_url else None
    path = config.get("csv_path")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return CsvOrgSource(f.read())


def refresh_org_from_source(db: Session, triggered_by: str) -> dict | None:
    """Fuehrt den Import aus der Quelle durch. Gibt die Zusammenfassung zurueck oder None,
    wenn keine Quelle konfiguriert ist. Fehler werden geworfen (Aufrufer entscheidet)."""
    from app.services.scheduler import get_schedule_config

    source = configured_source(get_schedule_config(db))
    if source is None:
        return None
    records: list[OrgRecord] = source.fetch()
    diff = apply_import(db, records, triggered_by=triggered_by)
    recompute_roles(db)
    return diff.summary


def last_import(db: Session) -> dict | None:
    log = db.execute(
        select(ImportLog).where(ImportLog.dry_run.is_(False), ImportLog.status == "ok").order_by(ImportLog.id.desc())
    ).scalars().first()
    if log is None:
        return None
    return {"finished_at": log.finished_at.isoformat() if log.finished_at else None, "triggered_by": log.triggered_by}
