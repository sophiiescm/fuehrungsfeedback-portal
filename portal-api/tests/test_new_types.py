from datetime import datetime, timedelta, timezone

import pytest

from app.models.person import OrgUnit, Person
from app.models.result import ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion
from app.services import evaluation, textanalysis
from app.services.survey_export import build_tsv, relevance_for


@pytest.fixture()
def version(db_session):
    t = SurveyTemplate(name="T")
    db_session.add(t)
    db_session.flush()
    v = SurveyVersion(survey_template_id=t.id, version_number=1)
    db_session.add(v)
    db_session.flush()
    d = Dimension(survey_version_id=v.id, name="D", sort_order=1)
    db_session.add(d)
    db_session.flush()
    q = {}
    q["nps"] = Question(survey_version_id=v.id, dimension_id=d.id, type=QuestionType.nps, text="NPS", sort_order=1)
    q["single"] = Question(survey_version_id=v.id, dimension_id=d.id, type=QuestionType.choice, text="E", options=["A", "B", "C"], sort_order=2)
    q["multi"] = Question(survey_version_id=v.id, dimension_id=d.id, type=QuestionType.choice, allow_multiple=True, text="M", options=["X", "Y", "Z"], sort_order=3)
    db_session.add_all(q.values())
    db_session.flush()
    q["free"] = Question(survey_version_id=v.id, dimension_id=None, type=QuestionType.freitext, text="F", sort_order=4,
                         show_if_question_id=q["nps"].id, show_if_operator="lt", show_if_value="7")
    q["free2"] = Question(survey_version_id=v.id, dimension_id=None, type=QuestionType.freitext, text="F2", sort_order=5)
    db_session.add_all([q["free"], q["free2"]])
    db_session.commit()
    db_session.refresh(v)
    return v, q


def test_export_maps_all_types_and_branching(version):
    v, q = version
    tsv = build_tsv(v)
    lines = tsv.splitlines()
    assert sum(1 for l in lines if l.startswith("A\t0\t") and l.split("\t")[2].isdigit()) == 11 + 3
    assert any(l.startswith("Q\tM\t") for l in lines) and sum(1 for l in lines if l.startswith("SQ\t")) == 3
    assert f"((Q{q['nps'].id}.NAOK < 7))" in tsv
    assert tsv.count("Q\tT\t") == 2  # mehrere Freitextfelder


def test_branching_on_later_question_is_ignored(version):
    v, q = version
    q["nps"].show_if_question_id = q["free2"].id
    q["nps"].show_if_operator, q["nps"].show_if_value = "eq", "1"
    assert relevance_for(q["nps"], {x.id: x for x in v.questions}) == "1"


def _target(db_session, version):
    v, q = version
    unit = OrgUnit(name="U", fachbereich="IT")
    db_session.add(unit)
    db_session.flush()
    boss = Person(personalnummer="B", vorname="B", nachname="B", org_unit_id=unit.id)
    db_session.add(boss)
    db_session.flush()
    now = datetime.now(timezone.utc)
    r = Round(name="R", survey_version_id=v.id, status=RoundStatus.geschlossen, start_at=now - timedelta(days=5), end_at=now)
    db_session.add(r)
    db_session.flush()
    t = RoundTarget(round_id=r.id, leader_person_id=boss.id, leader_code="FK-1", team_size_snapshot=5, evaluable=True)
    db_session.add(t)
    db_session.commit()
    return t


def test_evaluate_nps_choice_and_freetext_per_question(db_session, version):
    v, q = version
    t = _target(db_session, version)
    resp = []
    for nps, single, multi in [(10, "1", ["SQ001"]), (9, "1", ["SQ001", "SQ002"]), (3, "2", ["SQ002"]), (8, "3", [])]:
        r = {f"Q{q['nps'].id}": str(nps), f"Q{q['single'].id}": single,
             f"Q{q['free'].id}": "Kommunikation koennte besser sein" if nps < 7 else None,
             f"Q{q['free2'].id}": "Team ist gut"}
        for sq in multi:
            r[f"Q{q['multi'].id}[{sq}]"] = "Y"
        resp.append(r)
    rep = evaluation.evaluate_target(db_session, t, resp, None, set())
    aggs = {a.question_id: a for a in db_session.query(ResultAggregate).all()}
    assert aggs[q["single"].id].distribution == {"A": 2, "B": 1, "C": 1}
    assert aggs[q["multi"].id].distribution == {"X": 2, "Y": 2, "Z": 0} and aggs[q["multi"].id].n == 3
    assert aggs[q["nps"].id].n == 4
    # nur 1 Text fuer q["free"] (< Schwelle) -> nicht angezeigt; q["free2"] hat 4 Texte
    assert [g["question_id"] for g in rep.freetext] == [q["free2"].id]


def test_wordcloud_needs_three_distinct_answers():
    texts = ["Die Kommunikation ist schlecht", "Kommunikation fehlt oft", "Mehr Kommunikation bitte", "Sonderbarkeit einzeln"]
    words = {w["word"] for w in textanalysis.wordcloud(texts)}
    assert "Kommunikation" in words and "Sonderbarkeit" not in words


def test_wordcloud_counts_answers_not_repeats():
    assert textanalysis.wordcloud(["Kommunikation Kommunikation Kommunikation"]) == []


def test_categories_merge_small_groups():
    texts = ["Mehr Feedback und Kommunikation", "Gute Kommunikation im Meeting", "Transparente Information",
             "Weiterbildung waere schoen"]
    grouped = textanalysis.group_by_category(texts, textanalysis.categorize_keywords(texts))
    names = {g["category"] for g in grouped}
    assert "Kommunikation" in names and "Entwicklung" not in names  # 1 Text < Schwelle
    assert all(g["count"] >= 3 for g in grouped)


def test_compare_endpoint_traffic_light_and_suppression(client, db_session, version, seeded_users):
    from app.api.routes.reports import traffic_light

    assert traffic_light(0.3) == "gruen" and traffic_light(-0.3) == "rot" and traffic_light(0.0) == "gelb"
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    t = _target(db_session, version)
    d = client.get(f"/benchmark/compare?round_id={t.round_id}&groups=IT,Vertrieb", headers=h).json()
    assert d["groups"]["IT"]["suppressed"] is True  # nur 1 Fuehrungskraft
    assert client.put("/nps/reference", headers=h, json={"value": 31, "label": "Branche"}).json()["value"] == 31.0
    assert client.get("/nps/reference", headers=h).json()["label"] == "Branche"


def test_scale_labels_validated_and_exported(client, seeded_users, db_session):
    from app.services.survey_export import build_tsv
    from app.models.survey import SurveyVersion
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    tid = client.post("/surveys/templates", json={"name": "L"}, headers=h).json()["id"]
    vid = client.get("/surveys/templates", headers=h).json()[0]["versions"][0]["id"]
    labels = ["nie", "selten", "manchmal", "oft", "immer"]
    ok = client.post(f"/surveys/versions/{vid}/questions", headers=h,
                     json={"type": "likert", "text": "Q?", "scale_min": 1, "scale_max": 5, "scale_labels": labels})
    assert ok.status_code == 200 and ok.json()["scale_labels"] == labels
    bad = client.post(f"/surveys/versions/{vid}/questions", headers=h,
                      json={"type": "likert", "text": "Q2?", "scale_min": 1, "scale_max": 7, "scale_labels": labels})
    assert bad.status_code == 400
    tsv = build_tsv(db_session.get(SurveyVersion, vid))
    for i, l in enumerate(labels, start=1):
        assert any(line.startswith(f"A\t0\t{i}\t{l}\t") for line in tsv.splitlines())
