from app.models.person import Person, Role, RoleAssignment


def _h(client, pnr):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": pnr}).json()["access_token"]}


def _role_id(client, h, name):
    return next(r["id"] for r in client.get("/access/roles", headers=h).json() if r["name"] == name)


def test_default_roles_and_legacy_admin_has_full_access(client, seeded_users):
    h = _h(client, "T-ADMIN")
    roles = client.get("/access/roles", headers=h).json()
    assert {"Vollzugriff", "Umfrage & Auswertung", "Nur Auswertung"} <= {r["name"] for r in roles}
    me = client.get("/auth/me", headers=h).json()
    assert set(me["permissions"]) == {"surveys.manage", "rounds.manage", "results.view", "users.manage", "settings.manage"}


def test_view_only_admin_sees_results_but_cannot_change(client, seeded_users, db_session):
    h = _h(client, "T-ADMIN")
    viewer = seeded_users["employee"]
    rid = _role_id(client, h, "Nur Auswertung")
    r = client.put(f"/access/persons/{viewer.id}", json={"role_ids": [rid]}, headers=h)
    assert r.status_code == 200 and r.json()["permissions"] == ["results.view"]
    hv = _h(client, "T-MA")  # bekommt dadurch Admin-Zugang, aber nur Ansicht

    assert client.get("/rounds", headers=hv).status_code == 200
    assert client.get("/organisation/fachbereiche", headers=hv).status_code == 200
    assert client.get("/benchmark?round_id=1", headers=hv).status_code == 200
    assert client.get("/benchmark/export.csv?round_id=1", headers=hv).status_code == 200
    # alles andere: 403
    assert client.get("/surveys/templates", headers=hv).status_code == 403
    assert client.post("/surveys/templates", json={"name": "X"}, headers=hv).status_code == 403
    assert client.post("/rounds", json={}, headers=hv).status_code == 403
    assert client.get("/rounds/automation", headers=hv).status_code == 403
    assert client.get("/organisation/persons", headers=hv).status_code == 403
    assert client.get("/mail-templates", headers=hv).status_code == 403
    assert client.get("/access/roles", headers=hv).status_code == 403
    assert client.post("/rounds/1/evaluate", headers=hv).status_code == 403


def test_survey_manager_can_create_surveys_but_not_manage_users(client, seeded_users):
    h = _h(client, "T-ADMIN")
    rid = _role_id(client, h, "Umfrage & Auswertung")
    client.put(f"/access/persons/{seeded_users['employee'].id}", json={"role_ids": [rid]}, headers=h)
    hm = _h(client, "T-MA")
    assert client.post("/surveys/templates", json={"name": "Neu"}, headers=hm).status_code in (200, 201)
    assert client.get("/organisation/persons", headers=hm).status_code == 403


def test_custom_role_crud_and_lockout_protection(client, seeded_users, db_session):
    h = _h(client, "T-ADMIN")
    admin = seeded_users["admin"]
    full = _role_id(client, h, "Vollzugriff")
    # Admin bekommt explizit die Vollzugriffsrolle; danach darf sie ihm nicht entzogen werden (einziger Rechte-Verwalter)
    assert client.put(f"/access/persons/{admin.id}", json={"role_ids": [full]}, headers=h).status_code == 200
    assert client.put(f"/access/persons/{admin.id}", json={"role_ids": []}, headers=h).status_code == 409
    assert client.delete(f"/access/roles/{full}", headers=h).status_code == 409  # System-Rolle

    new = client.post("/access/roles", json={"name": "HR-Lesen", "permissions": ["results.view", "users.manage"]}, headers=h)
    assert new.status_code == 201
    assert client.post("/access/roles", json={"name": "HR-Lesen", "permissions": []}, headers=h).status_code == 409
    assert client.post("/access/roles", json={"name": "Kaputt", "permissions": ["erfunden"]}, headers=h).status_code == 400
    assert client.put(f"/access/roles/{new.json()['id']}", json={"name": "HR-Lesen", "permissions": ["results.view"]}, headers=h).status_code == 200

    # Inhaber verliert nach Loeschen der Rolle den Admin-Zugang (kein Vollzugriff durch Legacy-Regel)
    emp = seeded_users["employee"]
    client.put(f"/access/persons/{emp.id}", json={"role_ids": [new.json()["id"]]}, headers=h)
    assert client.delete(f"/access/roles/{new.json()['id']}", headers=h).status_code == 204
    assert not db_session.query(RoleAssignment).filter_by(person_id=emp.id, role=Role.admin).first()
