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
from sqlalchemy import select

from app.db import SessionLocal
from app.models.system import Setting
from app.services.org_import import apply_import
from app.services.org_source import CsvOrgSource
from app.services.roles import recompute_roles

logger = logging.getLogger(__name__)

SETTING_KEY = "org_import_schedule"
JOB_ID = "nightly_org_import"

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
    db = SessionLocal()
    try:
        config = get_schedule_config(db)
        csv_path = config.get("csv_path")
        if not config.get("enabled") or not csv_path:
            return
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
        records = CsvOrgSource(content).fetch()
        apply_import(db, records, triggered_by="scheduler")
        recompute_roles(db)
    except Exception:
        logger.exception("Naechtlicher Org-Import fehlgeschlagen")
    finally:
        db.close()


def _apply_schedule(scheduler: BackgroundScheduler, config: dict) -> None:
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    if config.get("enabled") and config.get("csv_path"):
        scheduler.add_job(run_nightly_import, CronTrigger.from_crontab(config["cron"]), id=JOB_ID)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    scheduler = BackgroundScheduler()
    db = SessionLocal()
    try:
        config = get_schedule_config(db)
    finally:
        db.close()
    _apply_schedule(scheduler, config)
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
