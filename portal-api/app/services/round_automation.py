"""Wiederkehrende Runden (z. B. halbjaehrlich) automatisch aus einer Vorlage anlegen.

Konfiguration in der `setting`-Tabelle (Schluessel `round_automation`), im Admin-UI
aenderbar. Der Lebenszyklus-Tick legt die naechste Runde `lead_days` vor dem Start
als `geplant` an; das Starten uebernimmt der bestehende Lebenszyklus-Tick.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.round import Round, RoundStatus
from app.models.survey import SurveyVersion
from app.models.system import Setting

SETTING_KEY = "round_automation"
DEFAULTS = {
    "enabled": False,
    "survey_version_id": None,
    "interval_months": 6,
    "next_start": None,  # ISO-Datum der naechsten Runde
    "duration_days": 28,
    "lead_days": 14,
    "name_pattern": "Feedback-Runde {half}/{year}",
    "reminder_days_before_end": [7, 2],
    "report_channel": "portal",
    "target_fachbereiche": None,
}


def get_config(db: Session) -> dict:
    s = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    return {**DEFAULTS, **(s.value if s else {})}


def set_config(db: Session, config: dict) -> dict:
    merged = {**DEFAULTS, **config}
    s = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    if s is None:
        db.add(Setting(key=SETTING_KEY, value=merged))
    else:
        s.value = merged
    db.commit()
    return merged


def add_months(d: date, months: int) -> date:
    idx = d.month - 1 + months
    year, month = d.year + idx // 12, idx % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def round_name(pattern: str, start: date) -> str:
    return pattern.format(year=start.year, half="H1" if start.month <= 6 else "H2",
                          quarter=f"Q{(start.month - 1) // 3 + 1}", month=start.month)


def run_automation(db: Session, now: datetime | None = None) -> Round | None:
    """Legt bei Bedarf die naechste Runde an. Gibt sie zurueck, sonst None."""
    now = now or datetime.now(timezone.utc)
    cfg = get_config(db)
    if not cfg["enabled"] or not cfg["next_start"] or not cfg["survey_version_id"]:
        return None
    if db.get(SurveyVersion, cfg["survey_version_id"]) is None:
        return None
    start_day = date.fromisoformat(cfg["next_start"])
    start_at = datetime.combine(start_day, time(6, 0), tzinfo=timezone.utc)
    if now < start_at - timedelta(days=int(cfg["lead_days"])):
        return None
    name = round_name(cfg["name_pattern"], start_day)
    existing = db.execute(select(Round).where(Round.name == name)).scalars().first()
    created = None
    if existing is None:
        created = Round(
            name=name, survey_version_id=cfg["survey_version_id"], start_at=start_at,
            end_at=start_at + timedelta(days=int(cfg["duration_days"])),
            reminder_days_before_end=cfg["reminder_days_before_end"],
            report_channel=cfg["report_channel"], target_fachbereiche=cfg["target_fachbereiche"],
            status=RoundStatus.geplant,
        )
        db.add(created)
    cfg["next_start"] = add_months(start_day, int(cfg["interval_months"])).isoformat()
    set_config(db, cfg)
    return created
