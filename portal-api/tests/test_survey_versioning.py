from datetime import datetime, timezone

import pytest

from app.models.round import Round, RoundStatus
from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion
from app.services.survey_versioning import VersionLockedError, clone_as_new_version, ensure_editable, sync_lock_status


def _make_version_with_content(db_session) -> SurveyVersion:
    tpl = SurveyTemplate(name="Standard")
    db_session.add(tpl)
    db_session.flush()
    version = SurveyVersion(survey_template_id=tpl.id, version_number=1)
    db_session.add(version)
    db_session.flush()
    dim = Dimension(survey_version_id=version.id, name="Kommunikation", sort_order=1)
    db_session.add(dim)
    db_session.flush()
    db_session.add(
        Question(
            survey_version_id=version.id, dimension_id=dim.id, type=QuestionType.likert,
            text="Frage 1", scale_min=1, scale_max=5, mandatory=True, sort_order=1,
        )
    )
    db_session.commit()
    db_session.refresh(version)
    return version


def test_draft_version_is_editable(db_session):
    version = _make_version_with_content(db_session)
    ensure_editable(db_session, version)  # wirft nicht


def test_version_locks_once_used_by_a_round(db_session):
    version = _make_version_with_content(db_session)
    round_ = Round(
        name="Testrunde", survey_version_id=version.id, status=RoundStatus.geplant,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db_session.add(round_)
    db_session.commit()

    sync_lock_status(db_session, version)
    with pytest.raises(VersionLockedError):
        ensure_editable(db_session, version)


def test_clone_creates_new_draft_version_with_copied_structure(db_session):
    version = _make_version_with_content(db_session)
    round_ = Round(
        name="Testrunde", survey_version_id=version.id, status=RoundStatus.geplant,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db_session.add(round_)
    db_session.commit()
    sync_lock_status(db_session, version)

    clone = clone_as_new_version(db_session, version)

    assert clone.version_number == 2
    assert clone.id != version.id
    assert len(clone.dimensions) == 1
    assert len(clone.questions) == 1
    assert clone.questions[0].dimension_id == clone.dimensions[0].id
    ensure_editable(db_session, clone)  # neue Version ist wieder editierbar
