"""Schwaerzung von Freitexten vor Anzeige/KI-Verarbeitung (CLAUDE.md
Anonymitaet Nr. 5): Namen aus den Org-Daten, E-Mail, Telefon,
Personalnummern. Rohtexte werden zufaellig gemischt."""

from __future__ import annotations

import random
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\w)(?:\+|00)?\d[\d\s/().-]{6,}\d")
PERSONALNUMMER = re.compile(r"\b[A-Z]{0,4}-?\d{4,}\b")


def build_name_pattern(names: set[str]) -> re.Pattern | None:
    parts = {n.strip() for n in names if n and len(n.strip()) >= 3}
    if not parts:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(p) for p in sorted(parts, key=len, reverse=True)) + r")\b", re.IGNORECASE)


def redact(text: str, name_pattern: re.Pattern | None, personalnummern: set[str] | None = None) -> str:
    out = EMAIL.sub("[E-Mail]", text)
    out = PHONE.sub("[Telefon]", out)
    for pnr in personalnummern or ():
        out = re.sub(re.escape(pnr), "[Personalnummer]", out, flags=re.IGNORECASE)
    out = PERSONALNUMMER.sub("[Personalnummer]", out)
    if name_pattern is not None:
        out = name_pattern.sub("[Name]", out)
    return out


def redact_and_shuffle(texts: list[str], name_pattern, personalnummern=None, rng: random.Random | None = None) -> list[str]:
    cleaned = [redact(t, name_pattern, personalnummern) for t in texts if t and t.strip()]
    (rng or random.SystemRandom()).shuffle(cleaned)
    return cleaned
