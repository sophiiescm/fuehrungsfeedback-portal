"""Austauschbarer KI-Provider fuer Freitext-Zusammenfassungen
(none | openai_compatible | anthropic). Fehler/Timeouts fuehren zu
'keine Zusammenfassung', nie zum Abbruch (TASKS.md Phase 5)."""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PROMPT = (
    "Fasse die folgenden anonymisierten Freitext-Rueckmeldungen zu einer Fuehrungskraft "
    "thematisch in 3-6 Stichpunkten zusammen. Nenne Themen, keine woertlichen Zitate, "
    "keine Namen und keine Rueckschluesse auf einzelne Personen. Antworte auf Deutsch.\n\n"
)


def _chat(prompt: str, max_tokens: int = 600) -> str | None:
    settings = get_settings()
    provider = settings.ai_provider
    if provider == "none":
        return None
    try:
        if provider == "openai_compatible":
            r = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json={"model": settings.ai_model, "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        if provider == "anthropic":
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.ai_api_key or "", "anthropic-version": "2023-06-01"},
                json={"model": settings.ai_model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"].strip()
    except Exception:
        logger.exception("KI-Aufruf fehlgeschlagen")
    return None


def summarize(texts: list[str]) -> str | None:
    if not texts:
        return None
    return _chat(PROMPT + "\n".join(f"- {t}" for t in texts))


def categorize(texts: list[str]) -> dict[str, str]:
    """Ordnet (bereits geschwaerzte) Texte festen Kategorien zu. KI nur wenn konfiguriert; die Antwort
    wird streng gegen die feste Kategorienliste geprueft, sonst Schluesselwort-Fallback je Text."""
    from app.services import textanalysis

    result = textanalysis.categorize_keywords(texts)
    if get_settings().ai_provider == "none" or not texts:
        return result
    cats = list(textanalysis.CATEGORIES) + [textanalysis.OTHER]
    prompt = (
        "Ordne jeden der folgenden anonymisierten Texte genau einer Kategorie aus dieser Liste zu: "
        + ", ".join(cats) + ". Antworte ausschliesslich mit einem JSON-Array von Kategorienamen in der "
        "Reihenfolge der Texte, ohne weiteren Text.\n\n" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    )
    raw = _chat(prompt, max_tokens=2000)
    try:
        arr = json.loads(raw[raw.index("["): raw.rindex("]") + 1]) if raw else []
    except ValueError:
        return result
    if len(arr) == len(texts):
        for t, c in zip(texts, arr):
            if c in cats:
                result[t] = c
    return result
