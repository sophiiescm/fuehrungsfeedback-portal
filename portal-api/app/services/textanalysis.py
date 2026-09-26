"""Auswertung geschwaerzter Freitexte: Wordcloud und Kategorisierung.

Rueckverfolgbarkeit: Ein Wort erscheint in der Wordcloud nur, wenn es in
mindestens `effective_threshold()` (>= 3) VERSCHIEDENEN Antworten vorkommt.
Eine Kategorie wird nur angezeigt, wenn sie mindestens so viele Texte enthaelt;
kleinere Kategorien werden in "Sonstiges" zusammengefuehrt.
"""

from __future__ import annotations

import re
from collections import Counter

from app.services.stats import effective_threshold

STOPWORDS = set(
    """aber alle allem allen aller alles also andere anderen auch auf aus bei bin bis bitte dabei dafuer dass dem den
der des die dies diese diesem diesen dieser dieses doch dort durch eine einem einen einer eines einmal etwas fuer gibt
habe haben hatte hier ihm ihn ihr jede jedem jeden jeder jedes kann kein keine koennte mehr mein meine muss nach nicht
noch ohne sehr sich sind sollte ueber unser unter waere waeren weil wenn werden wieder wird wurde zwar schon immer
wirklich manchmal leider danke wuerde eigentlich""".split()
)

WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}")
PLACEHOLDER = re.compile(r"\[[^\]]+\]")

# Feste Kategorien mit Schluesselwoertern (Fallback ohne KI; normalisiert: ae/oe/ue/ss, klein)
CATEGORIES: dict[str, tuple[str, ...]] = {
    "Kommunikation": ("kommunik", "informier", "transparen", "besprech", "meeting", "feedback", "erklaer", "zuhoer", "austausch"),
    "Wertschätzung": ("wertschaetz", "respekt", "lob", "anerkenn", "dank", "fair", "vertrau", "umgang"),
    "Entwicklung": ("entwickl", "weiterbild", "schulung", "karriere", "foerder", "lernen", "ziele", "talent"),
    "Zusammenarbeit": ("team", "zusammenarbeit", "konflikt", "kollegen", "unterstuetz", "gemeinsam"),
    "Organisation & Führung": ("entscheid", "priorit", "aufgabe", "verteil", "planung", "struktur", "erreichbar", "zeit", "fuehrung"),
}
OTHER = "Sonstiges"


def _norm(text: str) -> str:
    return text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def wordcloud(texts: list[str], max_words: int = 40) -> list[dict]:
    threshold = effective_threshold()
    docs_per_word: Counter[str] = Counter()
    display: dict[str, str] = {}
    for text in texts:
        seen = set()
        for w in WORD.findall(PLACEHOLDER.sub(" ", text)):
            key = _norm(w)
            if key in STOPWORDS:
                continue
            seen.add(key)
            display.setdefault(key, w)
        docs_per_word.update(seen)
    items = [{"word": display[k], "count": c} for k, c in docs_per_word.items() if c >= threshold]
    return sorted(items, key=lambda x: (-x["count"], x["word"]))[:max_words]


def categorize_keywords(texts: list[str]) -> dict[str, str]:
    """Text -> Kategorie per Schluesselwort (erste Kategorie mit den meisten Treffern)."""
    out = {}
    for t in texts:
        n = _norm(t)
        scores = {cat: sum(1 for kw in kws if kw in n) for cat, kws in CATEGORIES.items()}
        best = max(scores, key=lambda c: scores[c])
        out[t] = best if scores[best] > 0 else OTHER
    return out


def group_by_category(texts: list[str], assignment: dict[str, str]) -> list[dict]:
    """Gruppiert Texte nach Kategorie. Kategorien mit weniger als der Schwelle an Texten
    (auch 'Sonstiges' selbst) werden zusammengefuehrt; ist auch das zu klein, werden sie
    nicht angezeigt (die Texte bleiben in der ungruppierten Liste sichtbar)."""
    threshold = effective_threshold()
    buckets: dict[str, list[str]] = {}
    for t in texts:
        buckets.setdefault(assignment.get(t, OTHER), []).append(t)
    merged: dict[str, list[str]] = {}
    other: list[str] = list(buckets.pop(OTHER, []))
    for cat, items in buckets.items():
        if len(items) >= threshold:
            merged[cat] = items
        else:
            other += items
    if len(other) >= threshold:
        merged[OTHER] = other
    return [{"category": c, "count": len(v), "texts": v} for c, v in sorted(merged.items(), key=lambda kv: -len(kv[1]))]
