"""Sprachen fuer den Fragebogen. Standardsprache ist Deutsch; weitere Sprachen sind pro Fragebogen-Version
waehlbar (Codes wie in LimeSurvey). Fehlende Uebersetzungen fallen je Feld auf Deutsch zurueck."""

from __future__ import annotations

DEFAULT_LANGUAGE = "de"

LANGUAGES: dict[str, str] = {
    "de": "Deutsch", "en": "English", "tr": "Türkçe", "pl": "Polski", "ru": "Русский", "ro": "Română",
    "uk": "Українська", "ar": "العربية", "es": "Español", "fr": "Français", "it": "Italiano", "nl": "Nederlands",
    "pt": "Português", "bg": "Български", "hr": "Hrvatski", "cs": "Čeština", "hu": "Magyar", "el": "Ελληνικά",
    "sq": "Shqip", "bs": "Bosanski",
}

TRANSLATABLE_QUESTION_FIELDS = ("text", "help_text", "options", "scale_labels", "pole_label_min", "pole_label_max")


def catalog() -> list[dict]:
    return [{"code": c, "name": n} for c, n in LANGUAGES.items()]


def question_in(q, lang: str) -> dict:
    """Frage in `lang`; leere/fehlende Felder fallen auf die deutschen Werte zurueck."""
    base = {
        "text": q.text, "help_text": q.help_text or "", "options": list(q.options or []),
        "scale_labels": list(q.scale_labels or []), "pole_label_min": q.pole_label_min, "pole_label_max": q.pole_label_max,
    }
    if lang == DEFAULT_LANGUAGE:
        return base
    t = (q.translations or {}).get(lang) or {}
    out = dict(base)
    for k in ("text", "help_text", "pole_label_min", "pole_label_max"):
        if isinstance(t.get(k), str) and t[k].strip():
            out[k] = t[k].strip()
    opts = t.get("options")
    if isinstance(opts, list) and len(opts) == len(base["options"]) and all(isinstance(o, str) and o.strip() for o in opts):
        out["options"] = [o.strip() for o in opts]
    labels = t.get("scale_labels")
    if isinstance(labels, list) and len(labels) == len(base["scale_labels"]) and all(isinstance(o, str) and o.strip() for o in labels):
        out["scale_labels"] = [o.strip() for o in labels]
    return out


def dimension_name_in(d, lang: str) -> str:
    if lang == DEFAULT_LANGUAGE:
        return d.name
    name = ((d.translations or {}).get(lang) or {}).get("name")
    return name.strip() if isinstance(name, str) and name.strip() else d.name
