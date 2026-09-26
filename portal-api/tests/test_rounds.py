import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models.login_code import LoginCode
from app.models.notification import MailTemplate, Notification
from app.models.person import OrgUnit, Person, Role, RoleAssignment
from app.models.round import Participation, ParticipationStatus, Round, RoundStatus, RoundTarget
from app.models.survey import SurveyTemplate, SurveyVersion
from app.services import round_lifecycle
from app.services.login_codes import create_login_code, verify_login_code


class FakeLimeSurvey:
    def __init__(self, *a, **kw):
        self.copied = []
        self.next_sid = 5000

    def copy_survey(self, template_sid, name):
        self.next_sid += 1
        self.copied.append((template_sid, name))
        return self.next_sid

    def activate_tokens(self, sid):
        pass

    def add_participants(self, sid, participants):
        return [{"token": f"tok{sid}_{i}"} for i, _ in enumerate(participants)]

    def activate_survey(self, sid):
        pass

    def list_participants(self, sid):
        return [{"token": f"tok{sid}_0", "completed": "2026-01-02"}]

    def close(self):
        pass


@pytest.fixture()
def org(db_session, monkeypatch):
    monkeypatch.setattr(round_lifecycle, "LimeSurveyClient", FakeLimeSurvey)
    monkeypatch.setattr(round_lifecycle, "send_mail", lambda *a, **k: True, raising=False)
    import app.services.notifications as notif

    monkeypatch.setattr(notif, "send_mail", lambda *a, **k: True)

    unit = OrgUnit(name="U", fachbereich="IT")
    db_session.add(unit)
    db_session.flush()
    big_boss = Person(personalnummer="B1", vorname="Big", nachname="Boss", org_unit_id=unit.id, email="b@x.test")
    small_boss = Person(personalnummer="B2", vorname="Small", nachname="Boss", org_unit_id=unit.id, email="s@x.test")
    db_session.add_all([big_boss, small_boss])
    db_session.flush()
    for i in range(3):
        db_session.add(Person(personalnummer=f"M{i}", vorname="M", nachname=str(i), org_unit_id=unit.id,
                              manager_personalnummer="B1", email=None if i == 0 else f"m{i}@x.test"))
    db_session.add(Person(personalnummer="S1", vorname="S", nachname="1", org_unit_id=unit.id,
                          manager_personalnummer="B2", email="s1@x.test"))
    tpl = SurveyTemplate(name="T")
    db_session.add(tpl)
    db_session.flush()
    version = SurveyVersion(survey_template_id=tpl.id, version_number=1, limesurvey_template_sid=1)
    db_session.add(version)
    db_session.flush()
    db_session.add(MailTemplate(key="invitation", subject="Hi {{ round_name }}", body_html="<p>{{ feedback_link }}</p>"))
    db_session.add(MailTemplate(key="reminder", subject="Rem {{ days_left }}", body_html="x"))
    round_ = Round(name="R1", survey_version_id=version.id, status=RoundStatus.geplant,
                   start_at=datetime.now(timezone.utc) - timedelta(days=1),
                   end_at=datetime.now(timezone.utc) + timedelta(days=7),
                   reminder_days_before_end=[7, 2])
    db_session.add(round_)
    db_session.commit()
    return round_


def test_start_round_only_invites_teams_of_three_or_more(db_session, org):
    stats = round_lifecycle.start_round(db_session, org)
    assert stats["targets"] == 2
    assert stats["evaluable_targets"] == 1
    assert stats["participations"] == 3
    small = db_session.query(RoundTarget).filter_by(evaluable=False).one()
    assert small.limesurvey_sid is None
    assert db_session.query(Participation).filter_by(round_target_id=small.id).count() == 0
    assert org.status == RoundStatus.offen


def test_leader_code_is_not_derived_from_personalnummer(db_session, org):
    round_lifecycle.start_round(db_session, org)
    for t in db_session.query(RoundTarget).all():
        assert t.leader_code != f"FK-{t.leader.personalnummer}"  # Zufallscode, nicht ableitbar (kurze Nummern koennen zufaellig als Hex vorkommen)


def test_person_without_email_gets_login_code_and_portal_notification(db_session, org):
    round_lifecycle.start_round(db_session, org)
    m0 = db_session.query(Person).filter_by(personalnummer="M0").one()
    assert db_session.query(LoginCode).filter_by(person_id=m0.id).count() == 1
    assert db_session.query(Notification).filter_by(person_id=m0.id, type="invitation").count() == 1


def test_reminders_only_to_open_participants_and_only_once(db_session, org):
    round_lifecycle.start_round(db_session, org)
    first = db_session.query(Participation).first()
    first.status = ParticipationStatus.erledigt
    db_session.commit()
    assert round_lifecycle.send_due_reminders(db_session, org) == 2
    assert round_lifecycle.send_due_reminders(db_session, org) == 0


def test_reconcile_marks_completed_and_close_round(db_session, org):
    round_lifecycle.start_round(db_session, org)
    assert round_lifecycle.reconcile_open_participations(db_session, org) == 1
    round_lifecycle.close_round(db_session, org)
    assert org.status == RoundStatus.geschlossen


def test_start_requires_transferred_template(db_session, org):
    org.survey_version.limesurvey_template_sid = None
    db_session.commit()
    with pytest.raises(round_lifecycle.RoundLifecycleError):
        round_lifecycle.start_round(db_session, org)


def test_login_code_is_hashed_and_verifiable(db_session, seeded_users):
    person = seeded_users["employee"]
    rnd = Round(name="x", survey_version_id=1, start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc))
    tpl = SurveyTemplate(name="t")
    db_session.add(tpl)
    db_session.flush()
    db_session.add(SurveyVersion(survey_template_id=tpl.id, version_number=1))
    db_session.flush()
    rnd.survey_version_id = 1
    db_session.add(rnd)
    db_session.commit()
    code = create_login_code(db_session, person, rnd.id)
    stored = db_session.query(LoginCode).one()
    assert code not in stored.code_hash
    assert verify_login_code(db_session, person, code) is not None
    assert verify_login_code(db_session, person, "WRONG-CODE") is None


def _sig(sid, token):
    return hmac.new(get_settings().feedbackbridge_hmac_secret.encode(), f"{sid}:{token}".encode(), hashlib.sha256).hexdigest()


def test_webhook_rejects_bad_signature_and_accepts_good(client, db_session, org):
    round_lifecycle.start_round(db_session, org)
    p = db_session.query(Participation).first()
    sid = p.round_target.limesurvey_sid
    bad = client.post("/feedbacks/webhook/limesurvey-complete",
                      json={"sid": sid, "token": p.limesurvey_token, "signature": "nope"})
    assert bad.status_code == 401
    ok = client.post("/feedbacks/webhook/limesurvey-complete",
                     json={"sid": sid, "token": p.limesurvey_token, "signature": _sig(sid, p.limesurvey_token)})
    assert ok.json() == {"status": "ok"}
    db_session.refresh(p)
    assert p.status == ParticipationStatus.erledigt
    assert p.completed_date is not None


def test_my_feedbacks_only_shows_own_and_code_login_works(client, db_session, org):
    round_lifecycle.start_round(db_session, org)
    m1 = db_session.query(Person).filter_by(personalnummer="M1").one()
    db_session.add(RoleAssignment(person_id=m1.id, role=Role.mitarbeiter))
    db_session.commit()
    token = client.post("/auth/dev-login", json={"personalnummer": "M1"}).json()["access_token"]
    items = client.get("/feedbacks/mine", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(items) == 1 and items[0]["feedback_link"]

    m0 = db_session.query(Person).filter_by(personalnummer="M0").one()
    code = create_login_code(db_session, m0, org.id)
    ok = client.post("/auth/code-login", json={"personalnummer": "M0", "code": code})
    assert ok.status_code == 200
    bad = client.post("/auth/code-login", json={"personalnummer": "M0", "code": "XXXX-XXXX"})
    assert bad.status_code == 401


def test_dashboard_shows_rate_without_person_level_status(client, db_session, org, seeded_users):
    round_lifecycle.start_round(db_session, org)
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    d = client.get(f"/rounds/{org.id}/dashboard", headers=h).json()
    assert d["total_invited"] == 3
    assert all(set(t) == {"id","leader_person_id","leader_name","leader_code","team_size_snapshot","evaluable","completed_count","open_count"} for t in d["targets"])


def test_rounds_admin_only(client, seeded_users):
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-MA"}).json()["access_token"]}
    assert client.get("/rounds", headers=h).status_code == 403


def test_letters_html_contains_code_and_no_status(db_session, org):
    from app.services import pdf_letters

    round_lifecycle.start_round(db_session, org)
    html = pdf_letters.build_letters_html(db_session, org)
    assert "M0" in html and "data:image/png;base64" in html
    notices = pdf_letters.build_notices_html(db_session, org)
    assert "erledigt" not in notices and "offen" not in notices


def test_pdf_render_when_weasyprint_available(db_session, org):
    from app.services import pdf_letters

    try:
        pdf = pdf_letters.html_to_pdf("<p>x</p>")
    except (ImportError, OSError):
        pytest.skip("weasyprint-Systembibliotheken fehlen (lokal unter Windows), laeuft im Docker-Container")
    assert pdf.startswith(b"%PDF")


def test_code_login_rate_limited_after_five_failures(client, seeded_users):
    from app.services.rate_limit import login_limiter

    login_limiter._fails.clear()
    codes = [client.post("/auth/code-login", json={"personalnummer": "T-MA", "code": "BAD"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    login_limiter._fails.clear()


def test_admin_mutations_are_audit_logged_and_headers_set(client, db_session, seeded_users):
    from app.models.system import AuditLog

    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    r = client.post("/surveys/templates", headers=h, json={"name": "Audit"})
    assert db_session.query(AuditLog).filter(AuditLog.action == "POST /surveys/templates").count() == 1
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    client.get("/surveys/templates", headers=h)
    assert db_session.query(AuditLog).count() == 1  # Lesezugriffe werden nicht protokolliert
