"""Gestaltung des Reports (PDF/PowerPoint/Excel/CSV): welche Abschnitte, in welcher Reihenfolge,
mit welchen Ueberschriften. Konfiguration in `setting` (Schluessel `report_layout`), im Admin-UI pflegbar."""

from __future__ import annotations

import re
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system import Setting

SETTING_KEY = "report_layout"

# key -> (Standardtitel, Beschreibung, standardmaessig an)
SECTIONS: dict[str, tuple[str, str, bool]] = {
    "summary": ("Gesamtbild", "Gesamtwert, Vergleich zu Vorrunde und Unternehmen, Antwortzahl", True),
    "highlights": ("Stärken und Potenziale", "Die zwei besten und die zwei schwächsten Themen", True),
    "dimensions": ("Themen im Vergleich", "Tabelle der Dimensionen mit Balken und Vergleichswerten", True),
    "questions": ("Einzelfragen", "Kennzahlen je Frage (Skala, Auswahl, NPS)", False),
    "nps": ("Weiterempfehlung (NPS)", "Net Promoter Score mit Verteilung", True),
    "choices": ("Auswahlfragen", "Verteilung der Antworten bei Auswahlfragen", True),
    "ai_summary": ("Zusammenfassung der Freitexte", "KI-Zusammenfassung (falls eingerichtet)", True),
    "categories": ("Freitexte nach Themen", "Geschwärzte Freitexte, nach Themen gruppiert", True),
    "wordcloud": ("Häufige Begriffe", "Wörter, die in mindestens 3 Antworten vorkommen", False),
    "freetext": ("Alle Freitexte", "Alle geschwärzten Freitexte je Frage (auch in Excel/CSV)", False),
    "guide": ("Wie lese ich den Report?", "Kurze Erklärung der Werte und der Anonymität", True),
}

DEFAULT: dict = {
    "title": "Feedback-Report: {round}",
    "subtitle": "{leader} · {n} Antworten",
    "intro": "",
    "footer": "Vertraulich – nur für die bewertete Führungskraft bestimmt.",
    "accent": "#4f46e5",
    "columns": {"fachbereich": True, "unternehmen": True, "vorrunde": True, "median": True, "stddev": False, "minmax": False},
    "sections": [{"key": k, "enabled": v[2], "title": v[0]} for k, v in SECTIONS.items()],
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize(cfg: dict) -> dict:
    """Prueft/ergaenzt eine Konfiguration (unbekannte Abschnitte werden verworfen, fehlende angehaengt)."""
    out = deepcopy(DEFAULT)
    for k in ("title", "subtitle", "intro", "footer"):
        if isinstance(cfg.get(k), str):
            out[k] = cfg[k][:2000]
    if isinstance(cfg.get("accent"), str) and _HEX.match(cfg["accent"]):
        out["accent"] = cfg["accent"]
    if isinstance(cfg.get("columns"), dict):
        out["columns"] = {k: bool(cfg["columns"].get(k, v)) for k, v in DEFAULT["columns"].items()}
    seen, sections = set(), []
    for s in cfg.get("sections", []) if isinstance(cfg.get("sections"), list) else []:
        key = s.get("key") if isinstance(s, dict) else None
        if key in SECTIONS and key not in seen:
            seen.add(key)
            title = str(s.get("title") or SECTIONS[key][0])[:200]
            sections.append({"key": key, "enabled": bool(s.get("enabled", True)), "title": title})
    for key, (title, _d, on) in SECTIONS.items():
        if key not in seen:
            sections.append({"key": key, "enabled": on, "title": title})
    out["sections"] = sections
    return out


def get_layout(db: Session) -> dict:
    s = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    return normalize(s.value) if s else deepcopy(DEFAULT)


def set_layout(db: Session, cfg: dict) -> dict:
    cfg = normalize(cfg)
    s = db.execute(select(Setting).where(Setting.key == SETTING_KEY)).scalar_one_or_none()
    if s is None:
        db.add(Setting(key=SETTING_KEY, value=cfg))
    else:
        s.value = cfg
    db.commit()
    return cfg


def catalog() -> list[dict]:
    return [{"key": k, "title": v[0], "description": v[1]} for k, v in SECTIONS.items()]
