"""Naechtlicher Org-Import per Scheduler, konfigurierbar (CLAUDE.md
"Naechtlicher Import ist per Scheduler konfigurierbar").

Konfiguration liegt in der `setting`-Tabelle unter dem Schluessel
`org_import_schedule`, damit sie ohne Neustart per Admin-Endpunkt geaendert
werden kann: {"enabled": bool, "cron": "0 2 * * *", "csv_path": "..."}.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.db import SessionLocal
from app.models.system import Setting
from app.services.org_import import apply_import
from app.core.config import get_settings
from app.services.org_source import CsvOrgSource, ODataOrgSource
from app.services.roles import recompute_roles

logger = logging.getLogger(__name__)

SETTING_KEY = "org_import_schedule"
JOB_ID = "nightly_org_import"
ROUND_LIFECYCLE_JOB_ID = "round_lifecycle_tick"

_scheduler: BackgroundScheduler | None = None


def get_schedule_config(db) -> dict:
    setting = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    if setting is None:
        return {"enabled": False, "cron": "0 2 * * *", "csv_path": None}
    return setting.value


def set_schedule_config(db, config: dict) -> dict:
    setting = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    if setting is None:
        setting = Setting(key=SETTING_KEY, value=config)
        db.add(setting)
    else:
        setting.value = config
    db.commit()
    if _scheduler is not None:
        _apply_schedule(_scheduler, config)
    return config


def run_nightly_import() -> None:
    from app.services.org_sync import refresh_org_from_source

    db = SessionLocal()
    try:
        refresh_org_from_source(db, "scheduler")
    except Exception:
        logger.exception("Naechtlicher Org-Import fehlgeschlagen")
    finally:
        db.close()


def _apply_schedule(scheduler: BackgroundScheduler, config: dict) -> None:
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if config.get("enabled") and (config.get("csv_path") or config.get("source") == "odata"):
        scheduler.add_job(run_nightly_import, CronTrigger.from_crontab(config["cron"]), id=JOB_ID)


def run_round_lifecycle_tick() -> None:
    """Startet faellige Runden, gleicht offene Teilnahmen ab (Polling-Fallback
    fuer den FeedbackBridge-Webhook), verschickt faellige Erinnerungen und
    schliesst abgelaufene Runden. Siehe app.services.round_lifecycle."""
    from app.services.round_lifecycle import run_lifecycle_tick

    db = SessionLocal()
    try:
        result = run_lifecycle_tick(db)
        if any(result.values()):
            logger.info("Runden-Tick: %s", result)
    except Exception:
        logger.exception("Runden-Lebenszyklus-Tick fehlgeschlagen")
    finally:
        db.close()


def run_retention_job() -> None:
    from app.services.retention import run_retention

    db = SessionLocal()
    try:
        result = run_retention(db)
        if any(result.values()):
            logger.info("Datenminimierung: %s", result)
    except Exception:
        logger.exception("Datenminimierung fehlgeschlagen")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    scheduler = BackgroundScheduler()
    db = SessionLocal()
    try:
        config = get_schedule_config(db)
    finally:
        db.close()
    _apply_schedule(scheduler, config)
    scheduler.add_job(run_round_lifecycle_tick, IntervalTrigger(minutes=15), id=ROUND_LIFECYCLE_JOB_ID)
    scheduler.add_job(run_retention_job, CronTrigger(hour=3, minute=30), id="retention")
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
