"""Einfacher In-Memory-Ratelimit fuer den Code-Login (Schutz gegen Raten von
Einmalcodes). Pro Schluessel (Personalnummer bzw. IP): max. 5 Fehlversuche
je 15 Minuten. Hinweis: pro Prozess; bei mehreren API-Instanzen waere ein
gemeinsamer Speicher (z.B. Redis) noetig -- siehe docs/STATUS.md."""

from __future__ import annotations

import time
from collections import defaultdict


class FailureLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window = window_seconds
        self._fails: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.window
        self._fails[key] = [t for t in self._fails[key] if t > cutoff]
        return self._fails[key]

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_failures

    def fail(self, key: str) -> None:
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


login_limiter = FailureLimiter()
