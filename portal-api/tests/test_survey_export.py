from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion
from app.services.survey_export import MANDATORY_SURVEY_SETTINGS, build_tsv


def _make_version(db_session) -> SurveyVersion:
    tpl = SurveyTemplate(name="Führungsfeedback Standard")
    db_session.add(tpl)
    db_session.flush()
    version = SurveyVersion(survey_template_id=tpl.id, version_number=1)
    db_session.add(version)
    db_session.flush()
    dim = Dimension(survey_version_id=version.id, name="Kommunikation", sort_order=1)
    db_session.add(dim)
    db_session.flush()
    db_session.add_all(
        [
            Question(
                survey_version_id=version.id, dimension_id=dim.id, type=QuestionType.likert,
                text="Klar kommuniziert?", scale_min=1, scale_max=5,
                pole_label_min="nie", pole_label_max="immer", mandatory=True, sort_order=1,
            ),
            Question(
                survey_version_id=version.id, dimension_id=None, type=QuestionType.freitext,
                text="Was laeuft gut?", mandatory=False, sort_order=2,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(version)
    return version


def test_tsv_contains_mandatory_anonymity_settings(db_session):
    version = _make_version(db_session)
    tsv = build_tsv(version)
    for key, value in MANDATORY_SURVEY_SETTINGS.items():
        assert f"S\t\t{key}\t{value}" in tsv


def test_tsv_creates_group_per_dimension_and_catchall_for_ungrouped(db_session):
    version = _make_version(db_session)
    tsv = build_tsv(version)
    assert "G\t\tKommunikation\t" in tsv
    assert "G\t\tWeitere Fragen\t" in tsv


def test_tsv_likert_question_is_type_L_with_pole_labels(db_session):
    version = _make_version(db_session)
    tsv = build_tsv(version)
    lines = tsv.splitlines()
    q_line = next(l for l in lines if l.startswith("Q\tL\t"))
    assert "Klar kommuniziert?" in q_line
    assert any(l.startswith("A\t0\t1\tnie\t") for l in lines)
    assert any(l.startswith("A\t0\t5\timmer\t") for l in lines)


def test_tsv_freitext_question_is_type_T(db_session):
    version = _make_version(db_session)
    tsv = build_tsv(version)
    assert any(line.startswith("Q\tT\t") and "Was laeuft gut?" in line for line in tsv.splitlines())


def test_tsv_scale_width_is_configurable(db_session):
    tpl = SurveyTemplate(name="Test")
    db_session.add(tpl)
    db_session.flush()
    version = SurveyVersion(survey_template_id=tpl.id, version_number=1)
    db_session.add(version)
    db_session.flush()
    db_session.add(
        Question(
            survey_version_id=version.id, dimension_id=None, type=QuestionType.likert,
            text="7er Skala", scale_min=1, scale_max=7, pole_label_min="min", pole_label_max="max",
            mandatory=True, sort_order=1,
        )
    )
    db_session.commit()
    db_session.refresh(version)

    tsv = build_tsv(version)
    answer_lines = [l for l in tsv.splitlines() if l.startswith("A\t")]
    assert len(answer_lines) == 7
