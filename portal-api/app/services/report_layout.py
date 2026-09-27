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

# Anpassbare Festtexte des Reports: key -> (Bezeichnung, Standardtext, Hinweis)
TEXTS: dict[str, tuple[str, str, str]] = {
    "summary_scale": ("Gesamtwert: Skalenzusatz", "von 5", "steht hinter dem Gesamtwert"),
    "summary_prev": ("Gesamtbild: Vergleich Vorrunde", "zur Vorrunde", ""),
    "summary_company": ("Gesamtbild: Vergleich Unternehmen", "zum Unternehmen", ""),
    "summary_responses": ("Gesamtbild: Antworten", "Antworten", ""),
    "good_label": ("Stärken: Überschrift", "Das läuft gut", ""),
    "growth_label": ("Potenziale: Überschrift", "Hier steckt Potenzial", ""),
    "freetext_note": ("Hinweis unter Freitexten", "Freitexte sind von Namen und Kontaktdaten bereinigt und in zufälliger Reihenfolge – nicht rückverfolgbar.", "leer lassen = kein Hinweis"),
    "guide_body": ("Text „Wie lese ich den Report?“", "Die Werte reichen von 1 (trifft gar nicht zu) bis 5 (trifft voll zu) und sind Durchschnitte aller Antworten. Ergebnisse werden nur ab 3 Antworten gezeigt; Freitexte sind von Namen und Kontaktdaten bereinigt und nicht rückverfolgbar.", ""),
    "closing": ("Abschlusstext (Ende des Reports)", "", "z. B. Hinweis auf Ansprechpartner oder nächste Schritte"),
}

# Platzhalter, die in allen Texten, Titeln und Textbausteinen verwendet werden koennen
PLACEHOLDERS: dict[str, str] = {
    "leader": "Name der Führungskraft", "round": "Name der Runde", "n": "Anzahl Antworten", "date": "heutiges Datum",
    "overall": "Gesamtwert (Ø)", "overall_delta_prev": "Abstand zur Vorrunde", "company_avg": "Unternehmensschnitt (Ø)",
    "best_topic": "bestes Thema", "weak_topic": "schwächstes Thema", "nps": "NPS-Wert",
}

MAX_CUSTOM = 10
_CUSTOM = re.compile(r"^custom:[a-z0-9]{1,16}$")

DEFAULT: dict = {
    "title": "Feedback-Report: {round}",
    "subtitle": "{leader} · {n} Antworten",
    "intro": "",
    "footer": "Vertraulich – nur für die bewertete Führungskraft bestimmt.",
    "accent": "#004f23",
    "texts": {},
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
    if isinstance(cfg.get("texts"), dict):
        out["texts"] = {k: str(v)[:4000] for k, v in cfg["texts"].items() if k in TEXTS and isinstance(v, str) and v != TEXTS[k][1]}
    seen, sections, custom = set(), [], 0
    for s in cfg.get("sections", []) if isinstance(cfg.get("sections"), list) else []:
        key = s.get("key") if isinstance(s, dict) else None
        if key in SECTIONS and key not in seen:
            seen.add(key)
            title = str(s.get("title") or SECTIONS[key][0])[:200]
            sections.append({"key": key, "enabled": bool(s.get("enabled", True)), "title": title})
        elif isinstance(key, str) and _CUSTOM.match(key) and key not in seen and custom < MAX_CUSTOM:
            seen.add(key)
            custom += 1
            sections.append({"key": key, "enabled": bool(s.get("enabled", True)), "title": str(s.get("title") or "Textbaustein")[:200],
                             "body": str(s.get("body") or "")[:4000]})
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


def text_catalog() -> list[dict]:
    return [{"key": k, "label": v[0], "default": v[1], "hint": v[2]} for k, v in TEXTS.items()]


def placeholders() -> list[dict]:
    return [{"key": k, "label": v} for k, v in PLACEHOLDERS.items()]


def catalog() -> list[dict]:
    return [{"key": k, "title": v[0], "description": v[1]} for k, v in SECTIONS.items()]
