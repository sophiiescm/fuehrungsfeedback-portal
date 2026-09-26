from app.models.person import Person


def _h(client, pnr):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": pnr}).json()["access_token"]}


def test_actions_crud_only_own_and_team_visibility(client, seeded_users, db_session):
    leader, emp = seeded_users["leader"], seeded_users["employee"]
    emp.manager_personalnummer = leader.personalnummer
    db_session.commit()
    hl, he = _h(client, "T-FK"), _h(client, "T-MA")

    created = client.post("/actions", json={"title": "Wöchentliches Teamgespräch", "topic": "Kommunikation"}, headers=hl)
    assert created.status_code == 201
    hidden = client.post("/actions", json={"title": "Interne Notiz", "visible_to_team": False}, headers=hl).json()
    aid = created.json()["id"]

    team = client.get("/actions/team", headers=he).json()
    assert team["leader"] == leader.full_name and [a["title"] for a in team["actions"]] == ["Wöchentliches Teamgespräch"]

    # fremde Massnahme weder aenderbar noch loeschbar
    assert client.put(f"/actions/{aid}", json={"title": "Manipuliert!"}, headers=he).status_code == 404
    assert client.delete(f"/actions/{aid}", headers=he).status_code == 404

    upd = client.put(f"/actions/{aid}", json={"title": "Wöchentliches Teamgespräch", "status": "erledigt"}, headers=hl)
    assert upd.json()["status"] == "erledigt"
    assert client.delete(f"/actions/{hidden['id']}", headers=hl).status_code == 204
    assert len(client.get("/actions/mine", headers=hl).json()) == 1


def test_suggestions_empty_without_report(client, seeded_users):
    assert client.get("/actions/suggestions", headers=_h(client, "T-FK")).json() == []


def test_feedbacks_hidden_for_teams_below_threshold(client, seeded_users, db_session):
    from app.models.round import Participation, ParticipationStatus, Round, RoundStatus, RoundTarget
    from app.models.survey import SurveyTemplate, SurveyVersion
    from datetime import datetime, timezone
    t = SurveyTemplate(name="T")
    db_session.add(t)
    db_session.flush()
    v = SurveyVersion(survey_template_id=t.id, version_number=1)
    db_session.add(v)
    db_session.flush()
    r = Round(name="R", survey_version_id=v.id, status=RoundStatus.offen,
              start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    db_session.add(r)
    db_session.flush()
    lead, emp = seeded_users["leader"], seeded_users["employee"]
    small = RoundTarget(round_id=r.id, leader_person_id=lead.id, leader_code="FK-S", limesurvey_sid=1, team_size_snapshot=2, evaluable=False)
    db_session.add(small)
    db_session.flush()
    db_session.add(Participation(round_id=r.id, round_target_id=small.id, person_id=emp.id, status=ParticipationStatus.offen, limesurvey_token="x"))
    db_session.commit()
    assert client.get("/feedbacks/mine", headers=_h(client, "T-MA")).json() == []
