from datetime import datetime, timedelta, timezone

from app.models.notification import Notification
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import SurveyTemplate, SurveyVersion
from app.services.retention import run_retention


class FakeClient:
    deleted: list[int] = []

    def delete_survey(self, sid):
        FakeClient.deleted.append(sid)

    def close(self):
        pass


def test_retention_deletes_old_raw_surveys_and_notifications(db_session, seeded_users):
    FakeClient.deleted = []
    t = SurveyTemplate(name="T")
    db_session.add(t)
    db_session.flush()
    v = SurveyVersion(survey_template_id=t.id, version_number=1)
    db_session.add(v)
    db_session.flush()
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    old = Round(name="alt", survey_version_id=v.id, status=RoundStatus.berichtet,
                start_at=now - timedelta(days=200), end_at=now - timedelta(days=170))
    fresh = Round(name="neu", survey_version_id=v.id, status=RoundStatus.berichtet,
                  start_at=now - timedelta(days=40), end_at=now - timedelta(days=10))
    open_ = Round(name="offen", survey_version_id=v.id, status=RoundStatus.offen,
                  start_at=now - timedelta(days=200), end_at=now - timedelta(days=170))
    db_session.add_all([old, fresh, open_])
    db_session.flush()
    lead = seeded_users["leader"]
    for i, r in enumerate((old, fresh, open_)):
        db_session.add(RoundTarget(round_id=r.id, leader_person_id=lead.id, leader_code=f"FK-{i}", limesurvey_sid=100 + i,
                                   team_size_snapshot=5, evaluable=True))
    emp = seeded_users["employee"]
    db_session.add_all([
        Notification(person_id=emp.id, type="invitation", title="alt", body="x", created_at=now - timedelta(days=400)),
        Notification(person_id=emp.id, type="invitation", title="neu", body="x", created_at=now - timedelta(days=5)),
    ])
    db_session.commit()

    res = run_retention(db_session, now=now, client_factory=FakeClient)
    assert FakeClient.deleted == [100]  # nur abgeschlossene Runde ueber der Frist
    assert res["surveys_deleted"] == 1 and res["notifications"] == 1
    sids = {t.round_id: t.limesurvey_sid for t in db_session.query(RoundTarget)}
    assert sids[old.id] is None and sids[fresh.id] == 101 and sids[open_.id] == 102
