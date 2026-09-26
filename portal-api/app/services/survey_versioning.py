"""Versionierung von Umfragen (CLAUDE.md: 'eine Runde friert eine Version
ein'; TASKS.md Phase 3: 'Version ist nach Nutzung in einer Runde gesperrt').
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.round import Round
from app.models.survey import Dimension, Question, SurveyVersion, SurveyVersionStatus


class VersionLockedError(RuntimeError):
    pass


def sync_lock_status(db: Session, version: SurveyVersion) -> SurveyVersion:
    """Sperrt die Version automatisch, sobald sie von mindestens einer Runde
    verwendet wird (unabhaengig vom Rundenstatus -- sobald eine Runde sie
    referenziert, darf die Struktur nicht mehr rueckwirkend veraendert werden)."""
    if version.status == SurveyVersionStatus.entwurf:
        in_use = db.execute(
            select(Round.id).where(Round.survey_version_id == version.id).limit(1)
        ).scalar_one_or_none()
        if in_use is not None:
            version.status = SurveyVersionStatus.gesperrt
            db.commit()
    return version


def ensure_editable(db: Session, version: SurveyVersion) -> None:
    sync_lock_status(db, version)
    if version.status != SurveyVersionStatus.entwurf:
        raise VersionLockedError(
            "Diese Umfrageversion ist bereits in einer Runde verwendet worden und daher "
            "gesperrt. Bitte 'Als neue Version bearbeiten' verwenden."
        )


def clone_as_new_version(db: Session, version: SurveyVersion) -> SurveyVersion:
    latest_number = version.survey_template.versions[-1].version_number if version.survey_template.versions else version.version_number
    new_version = SurveyVersion(
        survey_template_id=version.survey_template_id,
        version_number=latest_number + 1,
        status=SurveyVersionStatus.entwurf,
        languages=list(version.languages or []),
    )
    db.add(new_version)
    db.flush()

    dimension_id_map: dict[int, int] = {}
    for dim in sorted(version.dimensions, key=lambda d: d.sort_order):
        new_dim = Dimension(survey_version_id=new_version.id, name=dim.name, sort_order=dim.sort_order, translations=dim.translations)
        db.add(new_dim)
        db.flush()
        dimension_id_map[dim.id] = new_dim.id

    new_questions: dict[int, Question] = {}
    for q in sorted(version.questions, key=lambda q: q.sort_order):
        new_q = Question(
                survey_version_id=new_version.id,
                dimension_id=dimension_id_map.get(q.dimension_id) if q.dimension_id else None,
                type=q.type,
                text=q.text,
                scale_min=q.scale_min,
                scale_max=q.scale_max,
                pole_label_min=q.pole_label_min,
                scale_labels=q.scale_labels,
                translations=q.translations,
                pole_label_max=q.pole_label_max,
                mandatory=q.mandatory,
                sort_order=q.sort_order,
                help_text=q.help_text,
                options=q.options,
                allow_multiple=q.allow_multiple,
                show_if_operator=q.show_if_operator,
                show_if_value=q.show_if_value,
        )
        db.add(new_q)
        new_questions[q.id] = new_q
    db.flush()
    for q in version.questions:  # Verzweigungen auf die neuen Fragen umbiegen
        if q.show_if_question_id in new_questions:
            new_questions[q.id].show_if_question_id = new_questions[q.show_if_question_id].id

    db.commit()
    db.refresh(new_version)
    return new_version
