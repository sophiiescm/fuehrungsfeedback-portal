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
