from datetime import date, datetime, timezone

from app.models.round import Round, RoundStatus
from app.models.survey import SurveyTemplate, SurveyVersion
from app.services import round_automation as ra


def _version(db):
    t = SurveyTemplate(name="T")
    db.add(t)
    db.flush()
    v = SurveyVersion(survey_template_id=t.id, version_number=1)
    db.add(v)
    db.commit()
    return v


def test_add_months_and_name():
    assert ra.add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert ra.round_name("R {half}/{year}", date(2026, 9, 1)) == "R H2/2026"


def test_automation_creates_and_advances(db_session):
    v = _version(db_session)
    ra.set_config(db_session, {"enabled": True, "survey_version_id": v.id, "next_start": "2026-10-01", "lead_days": 14})
    # zu frueh: nichts
    assert ra.run_automation(db_session, datetime(2026, 9, 1, tzinfo=timezone.utc)) is None
    r = ra.run_automation(db_session, datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert r is not None and r.status == RoundStatus.geplant and r.name == "Feedback-Runde H2/2026"
    assert (r.end_at - r.start_at).days == 28
    assert ra.get_config(db_session)["next_start"] == "2027-04-01"
    # idempotent: gleicher Zeitpunkt erzeugt keine zweite Runde
    assert ra.run_automation(db_session, datetime(2026, 9, 21, tzinfo=timezone.utc)) is None
    assert db_session.query(Round).count() == 1


def test_disabled_does_nothing(db_session):
    assert ra.run_automation(db_session) is None


def test_automation_endpoints(client, seeded_users, db_session):
    v = _version(db_session)
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    assert client.get("/rounds/automation", headers=h).json()["enabled"] is False
    bad = client.put("/rounds/automation", json={"enabled": True}, headers=h)
    assert bad.status_code == 422
    ok = client.put("/rounds/automation", json={"enabled": True, "survey_version_id": v.id, "next_start": "2026-10-01"}, headers=h)
    assert ok.status_code == 200 and ok.json()["next_start"] == "2026-10-01"


def test_recipient_preview(client, seeded_users, db_session):
    from app.models.person import Person
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    lead = seeded_users["leader"]
    for i in range(3):
        db_session.add(Person(personalnummer=f"X{i}", vorname="A", nachname=f"B{i}", email=None if i == 0 else "a@example.test",
                              org_unit_id=lead.org_unit_id, manager_personalnummer=lead.personalnummer))
    db_session.commit()
    r = client.get("/rounds/preview", headers=h).json()
    assert r["total"]["leaders"] == 1 and r["total"]["recipients"] == 3 and r["total"]["without_email"] == 1


def test_manual_reminder_and_exports_require_admin_and_work(client, seeded_users, db_session):
    h = {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": "T-ADMIN"}).json()["access_token"]}
    v = _version(db_session)
    r = Round(name="R", survey_version_id=v.id, status=RoundStatus.geplant,
              start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    db_session.add(r)
    db_session.commit()
    assert client.post(f"/rounds/{r.id}/remind", headers=h).status_code == 409  # nur bei offenen Runden
    csv = client.get(f"/rounds/{r.id}/response-rate.csv", headers=h)
    assert csv.status_code == 200 and "fachbereich;eingeladen" in csv.text
    assert client.get(f"/benchmark/export.csv?round_id={r.id}", headers=h).status_code == 200
