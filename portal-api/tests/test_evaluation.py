import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.models.person import OrgUnit, Person, Role, RoleAssignment
from app.models.result import Report, ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion
from app.services import evaluation
from app.services.redaction import build_name_pattern, redact, redact_and_shuffle
from app.services.stats import compute_stats, effective_threshold


def test_stats_values():
    s = compute_stats([1, 2, 3, 4, 5])
    assert (s.n, s.min, s.max, s.mean, s.median) == (5, 1, 5, 3.0, 3.0)
    assert s.stddev == pytest.approx(1.414, abs=0.001)
    assert s.distribution == {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1}


def test_stats_suppressed_below_threshold():
    assert compute_stats([5, 5]) is None
    assert compute_stats([5, 5, 5]) is not None


def test_threshold_never_below_three(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "min_responses_for_report", 1)
    assert effective_threshold() == 3
    assert compute_stats([1, 2]) is None


def test_redaction_removes_names_mail_phone_and_pnr():
    pattern = build_name_pattern({"Meier", "Anna"})
    out = redact("Frau Meier (anna.meier@firma.de, 0171 1234567, P00123) ist toll", pattern, {"P00123"})
    for leak in ("Meier", "@", "1234567", "P00123"):
        assert leak not in out
    assert "[Name]" in out and "[E-Mail]" in out


def test_shuffle_changes_order_but_keeps_texts():
    texts = [f"Text {i}" for i in range(30)]
    out = redact_and_shuffle(texts, None, rng=random.Random(1))
    assert sorted(out) == sorted(texts) and out != texts


@pytest.fixture()
def setup(db_session):
    unit = OrgUnit(name="U", fachbereich="IT")
    db_session.add(unit)
    db_session.flush()
    boss = Person(personalnummer="B1", vorname="Bea", nachname="Chef", org_unit_id=unit.id, email="b@x.test")
    db_session.add(boss)
    db_session.flush()
    db_session.add(RoleAssignment(person_id=boss.id, role=Role.fuehrungskraft))
    tpl = SurveyTemplate(name="T")
    db_session.add(tpl)
    db_session.flush()
    v = SurveyVersion(survey_template_id=tpl.id, version_number=1)
    db_session.add(v)
    db_session.flush()
    dim = Dimension(survey_version_id=v.id, name="Kommunikation", sort_order=1)
    db_session.add(dim)
    db_session.flush()
    q1 = Question(survey_version_id=v.id, dimension_id=dim.id, type=QuestionType.likert, text="A", sort_order=1)
    q2 = Question(survey_version_id=v.id, dimension_id=dim.id, type=QuestionType.likert, text="B", sort_order=2)
    qt = Question(survey_version_id=v.id, dimension_id=None, type=QuestionType.freitext, text="F", sort_order=3)
    db_session.add_all([q1, q2, qt])
    now = datetime.now(timezone.utc)
    rnd = Round(name="R", survey_version_id=v.id, status=RoundStatus.geschlossen, start_at=now - timedelta(days=9), end_at=now)
    db_session.add(rnd)
    db_session.flush()
    t = RoundTarget(round_id=rnd.id, leader_person_id=boss.id, leader_code="FK-X", team_size_snapshot=4, evaluable=True)
    db_session.add(t)
    db_session.commit()
    return dict(boss=boss, q1=q1, q2=q2, qt=qt, target=t, rnd=rnd)


def _responses(s, n, texts=True):
    return [{f"Q{s['q1'].id}": str(3 + i % 2), f"Q{s['q2'].id}": "4", f"Q{s['qt'].id}": f"Bea Chef ist gut {i}" if texts else None}
            for i in range(n)]


def test_two_responses_produce_no_report(db_session, setup):
    rep = evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 2), None, set())
    assert rep.suppressed and rep.freetext is None
    assert db_session.query(ResultAggregate).count() == 0


def test_three_responses_produce_aggregates_and_redacted_freetext(db_session, setup):
    pattern = build_name_pattern({"Bea", "Chef"})
    rep = evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 4), pattern, set())
    assert not rep.suppressed and rep.n_responses == 4
    assert db_session.query(ResultAggregate).filter(ResultAggregate.dimension_id.is_not(None)).count() == 1
    assert len(rep.freetext) == 4 and all("Bea" not in t and "Chef" not in t for t in rep.freetext)


def _token(client, pnr):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": pnr}).json()["access_token"]}


def test_report_visible_only_to_own_leader(client, db_session, setup, seeded_users):
    evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 4), None, set())
    setup["rnd"].status = RoundStatus.ausgewertet
    db_session.commit()
    tid = setup["target"].id
    assert client.get(f"/reports/{tid}", headers=_token(client, "B1")).json()["available"] is True
    for other in ("T-ADMIN", "T-FK", "T-MA"):  # auch Admins duerfen fremde Reports nicht sehen
        assert client.get(f"/reports/{tid}", headers=_token(client, other)).status_code == 404


def test_suppressed_report_shows_hint(client, db_session, setup):
    evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 2), None, set())
    setup["rnd"].status = RoundStatus.ausgewertet
    db_session.commit()
    d = client.get(f"/reports/{setup['target'].id}", headers=_token(client, "B1")).json()
    assert d["available"] is False and "Anonymität" in d["message"]
    assert "dimensions" not in d


def test_benchmark_pseudonymised_and_small_groups_suppressed(client, db_session, setup, seeded_users):
    evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 4), None, set())
    out = client.get(f"/benchmark?round_id={setup['rnd'].id}", headers=_token(client, "T-ADMIN")).json()
    assert out["IT"]["suppressed"] is True  # nur 1 Fuehrungskraft < 3
    assert "Chef" not in json.dumps(out)


def test_trend_and_previous_round_delta(client, db_session, setup):
    now = datetime.now(timezone.utc)
    old = Round(name="Alt", survey_version_id=setup["rnd"].survey_version_id, status=RoundStatus.berichtet,
                start_at=now - timedelta(days=200), end_at=now - timedelta(days=190))
    db_session.add(old)
    db_session.flush()
    ot = RoundTarget(round_id=old.id, leader_person_id=setup["boss"].id, leader_code="FK-Y", team_size_snapshot=4, evaluable=True)
    db_session.add(ot)
    db_session.commit()
    evaluation.evaluate_target(db_session, ot, [{f"Q{setup['q1'].id}": "2", f"Q{setup['q2'].id}": "2"}] * 3, None, set())
    evaluation.evaluate_target(db_session, setup["target"], _responses(setup, 4), None, set())
    setup["rnd"].status = RoundStatus.ausgewertet
    db_session.commit()
    h = _token(client, "B1")
    d = client.get(f"/reports/{setup['target'].id}", headers=h).json()
    assert d["dimensions"][0]["vorrunde"]["delta"] > 0
    assert len(client.get("/reports/mine/trend", headers=h).json()["series"]["Kommunikation"]) == 2
