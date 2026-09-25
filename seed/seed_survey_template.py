#!/usr/bin/env python3
"""Legt die mitgelieferte Beispiel-Umfrage "Führungsfeedback Standard" an
(TASKS.md Phase 3: "ca. 20 Likert-Fragen in 5 Dimensionen und 3
Freitextfragen"). Idempotent: überspringt, wenn die Vorlage schon existiert.

Verwendung (im portal-api-Verzeichnis, mit aktivierter venv, DB erreichbar):
    python ../seed/seed_survey_template.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "portal-api"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion  # noqa: E402

TEMPLATE_NAME = "Führungsfeedback Standard"

DIMENSIONS: dict[str, list[str]] = {
    "Kommunikation": [
        "Meine Führungskraft kommuniziert Erwartungen klar und verständlich.",
        "Meine Führungskraft informiert das Team rechtzeitig über wichtige Entscheidungen.",
        "Meine Führungskraft hört aktiv zu, wenn ich etwas anspreche.",
        "Meine Führungskraft gibt in Besprechungen allen die Möglichkeit, sich einzubringen.",
    ],
    "Wertschätzung": [
        "Meine Führungskraft erkennt gute Leistungen an.",
        "Ich fühle mich von meiner Führungskraft respektiert.",
        "Meine Führungskraft nimmt sich Zeit für persönliche Anliegen.",
        "Meine Führungskraft geht fair mit allen Teammitgliedern um.",
    ],
    "Entwicklung": [
        "Meine Führungskraft unterstützt meine fachliche Weiterentwicklung.",
        "Meine Führungskraft gibt mir konstruktives, hilfreiches Feedback.",
        "Meine Führungskraft bespricht mit mir regelmäßig meine Ziele.",
        "Meine Führungskraft ermutigt mich, Neues auszuprobieren.",
    ],
    "Entscheidungsfindung": [
        "Meine Führungskraft trifft Entscheidungen nachvollziehbar.",
        "Meine Führungskraft bezieht das Team angemessen in Entscheidungen ein.",
        "Meine Führungskraft steht zu getroffenen Entscheidungen.",
        "Meine Führungskraft reagiert besonnen auf schwierige Situationen.",
    ],
    "Zusammenarbeit": [
        "Meine Führungskraft fördert die Zusammenarbeit im Team.",
        "Meine Führungskraft löst Konflikte im Team konstruktiv.",
        "Meine Führungskraft ist bei Bedarf ansprechbar und erreichbar.",
        "Meine Führungskraft schafft ein Arbeitsumfeld, in dem ich mich wohlfühle.",
    ],
}

FREITEXT_FRAGEN = [
    "Was schätzen Sie besonders an der Zusammenarbeit mit Ihrer Führungskraft?",
    "Wo sehen Sie Verbesserungspotential?",
    "Gibt es weitere Anmerkungen, die Sie mitteilen möchten?",
]


def seed() -> SurveyTemplate:
    db = SessionLocal()
    try:
        existing = db.execute(
            select(SurveyTemplate).where(SurveyTemplate.name == TEMPLATE_NAME)
        ).scalar_one_or_none()
        if existing:
            print(f"Vorlage '{TEMPLATE_NAME}' existiert bereits (id={existing.id}), übersprungen.")
            return existing

        template = SurveyTemplate(name=TEMPLATE_NAME)
        db.add(template)
        db.flush()
        version = SurveyVersion(survey_template_id=template.id, version_number=1)
        db.add(version)
        db.flush()

        question_order = 1
        for dim_order, (dim_name, questions) in enumerate(DIMENSIONS.items(), start=1):
            dimension = Dimension(survey_version_id=version.id, name=dim_name, sort_order=dim_order)
            db.add(dimension)
            db.flush()
            for text in questions:
                db.add(
                    Question(
                        survey_version_id=version.id,
                        dimension_id=dimension.id,
                        type=QuestionType.likert,
                        text=text,
                        scale_min=1,
                        scale_max=5,
                        pole_label_min="Trifft gar nicht zu",
                        pole_label_max="Trifft voll zu",
                        mandatory=True,
                        sort_order=question_order,
                    )
                )
                question_order += 1

        for text in FREITEXT_FRAGEN:
            db.add(
                Question(
                    survey_version_id=version.id,
                    dimension_id=None,
                    type=QuestionType.freitext,
                    text=text,
                    mandatory=False,
                    sort_order=question_order,
                )
            )
            question_order += 1

        db.commit()
        total_questions = question_order - 1
        print(
            f"Vorlage '{TEMPLATE_NAME}' angelegt (id={template.id}, version={version.id}): "
            f"{len(DIMENSIONS)} Dimensionen, {total_questions} Fragen "
            f"({total_questions - len(FREITEXT_FRAGEN)} Likert, {len(FREITEXT_FRAGEN)} Freitext)."
        )
        return template
    finally:
        db.close()


if __name__ == "__main__":
    seed()
