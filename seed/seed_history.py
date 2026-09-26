#!/usr/bin/env python3
"""Zwei abgeschlossene historische Runden mit SIMULIERTEN Antworten (fiktiv),
fuer Trend und Benchmark (CLAUDE.md 'Seed-Skript'). Voraussetzung: Org-Import
(seed/generate_org_csv.py) und Vorlage (seed_survey_template.py) sind erfolgt.

Die Antworten werden ueber dieselbe Auswertungslogik wie im Echtbetrieb
(app.services.evaluation.evaluate_target) verarbeitet, inkl. Berichtsschwelle:
ca. 5% der Fuehrungskraefte bekommen bewusst nur 2 Antworten (kein Report).

    cd portal-api && .venv/Scripts/python ../seed/seed_history.py
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal-api"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.person import Person  # noqa: E402
from app.models.round import Round, RoundStatus, RoundTarget  # noqa: E402
from app.models.survey import QuestionType, SurveyVersion  # noqa: E402
from app.services.evaluation import evaluate_target  # noqa: E402

ROUNDS = [("Historisch H2/2025", datetime(2025, 9, 15, tzinfo=timezone.utc), datetime(2025, 10, 15, tzinfo=timezone.utc), 0.0),
          ("Historisch H1/2026", datetime(2026, 3, 15, tzinfo=timezone.utc), datetime(2026, 4, 15, tzinfo=timezone.utc), 0.15)]
TEXTS = ["Die Kommunikation im Team koennte klarer sein.", "Sehr wertschaetzender Umgang, danke.",
         "Mehr Entwicklungsgespraeche waeren hilfreich.", "Entscheidungen werden gut erklaert.",
         "Mehr Zeit fuer persoenliche Anliegen waere schoen.", "Faire Verteilung der Aufgaben."]


def main() -> None:
    rng = random.Random(7)
    db = SessionLocal()
    version = db.execute(select(SurveyVersion).order_by(SurveyVersion.id)).scalars().first()
    if version is None:
        sys.exit("Keine Umfragevorlage: erst seed_survey_template.py ausfuehren")
    if db.execute(select(Round).where(Round.name == ROUNDS[0][0])).scalar_one_or_none():
        print("Historische Runden existieren bereits, uebersprungen.")
        return

    reports = {p.manager_personalnummer for p in db.execute(select(Person).where(Person.aktiv.is_(True))).scalars() if p.manager_personalnummer}
    leaders = [p for p in db.execute(select(Person).where(Person.aktiv.is_(True))).scalars() if p.personalnummer in reports]
    team_size = {}
    for p in db.execute(select(Person).where(Person.aktiv.is_(True))).scalars():
        if p.manager_personalnummer:
            team_size[p.manager_personalnummer] = team_size.get(p.manager_personalnummer, 0) + 1
    leaders = [l for l in leaders if team_size[l.personalnummer] >= 3]
    quality = {l.id: {d.id: rng.gauss(3.5, 0.5) for d in version.dimensions} for l in leaders}

    for name, start, end, drift in ROUNDS:
        rnd = Round(name=name, survey_version_id=version.id, status=RoundStatus.berichtet, start_at=start, end_at=end)
        db.add(rnd)
        db.flush()
        for l in leaders:
            n_resp = 2 if rng.random() < 0.05 else max(3, round(team_size[l.personalnummer] * rng.uniform(0.6, 1.0)))
            t = RoundTarget(round_id=rnd.id, leader_person_id=l.id, leader_code=f"FK-{rng.randrange(16**8):08X}",
                            team_size_snapshot=team_size[l.personalnummer], evaluable=True)
            db.add(t)
            db.flush()
            responses = []
            for _ in range(n_resp):
                r = {}
                for q in version.questions:
                    if q.type == QuestionType.freitext:
                        r[f"Q{q.id}"] = rng.choice(TEXTS) if rng.random() < 0.7 else None
                    else:
                        mu = quality[l.id].get(q.dimension_id, 3.5) + drift + rng.gauss(0, 0.4)
                        r[f"Q{q.id}"] = str(min(5, max(1, round(mu + rng.gauss(0, 0.8)))))
                responses.append(r)
            evaluate_target(db, t, responses, None, set())
        print(f"{name}: {len(leaders)} Fuehrungskraefte")
    db.close()


if __name__ == "__main__":
    main()
