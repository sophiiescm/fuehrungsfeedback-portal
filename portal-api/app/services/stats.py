"""Statistik pro Frage/Dimension (CLAUDE.md 'Auswertung') und
Anonymitaetsschwelle. Die Schwelle ist konfigurierbar, aber nie < 3."""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass

from app.core.config import get_settings

ABSOLUTE_MIN_THRESHOLD = 3


def effective_threshold() -> int:
    return max(ABSOLUTE_MIN_THRESHOLD, get_settings().min_responses_for_report)


@dataclass
class Stats:
    n: int
    min: float
    max: float
    mean: float
    median: float
    stddev: float
    distribution: dict[str, int]


def compute_stats(values: list[float]) -> Stats | None:
    """Gibt None zurueck, wenn n unter der Berichtsschwelle liegt (Unterdrueckung)."""
    if len(values) < effective_threshold():
        return None
    dist = Counter(str(int(round(v))) for v in values)
    return Stats(
        n=len(values),
        min=min(values),
        max=max(values),
        mean=round(statistics.fmean(values), 3),
        median=float(statistics.median(values)),
        stddev=round(statistics.pstdev(values), 3),
        distribution=dict(sorted(dist.items())),
    )
