"""Austauschbarer KI-Provider fuer Freitext-Zusammenfassungen
(none | openai_compatible | anthropic). Fehler/Timeouts fuehren zu
'keine Zusammenfassung', nie zum Abbruch (TASKS.md Phase 5)."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PROMPT = (
    "Fasse die folgenden anonymisierten Freitext-Rueckmeldungen zu einer Fuehrungskraft "
    "thematisch in 3-6 Stichpunkten zusammen. Nenne Themen, keine woertlichen Zitate, "
    "keine Namen und keine Rueckschluesse auf einzelne Personen. Antworte auf Deutsch.\n\n"
)


def summarize(texts: list[str]) -> str | None:
    settings = get_settings()
    provider = settings.ai_provider
    if provider == "none" or not texts:
        return None
    prompt = PROMPT + "\n".join(f"- {t}" for t in texts)
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
                json={"model": settings.ai_model, "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"].strip()
    except Exception:
        logger.exception("KI-Zusammenfassung fehlgeschlagen")
    return None
