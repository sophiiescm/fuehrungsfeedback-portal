import io

CSV_HEADER = "personalnummer;vorname;nachname;email;org_einheit;fachbereich;manager_personalnummer;standort;aktiv"


def _auth_headers(client, personalnummer: str) -> dict:
    response = client.post("/auth/dev-login", json={"personalnummer": personalnummer})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# SAP-Exporte sind vollstaendige Snapshots: wer darin fehlt, gilt als
# ausgeschieden (siehe compute_diff). Der eingeloggte Test-Admin wird daher in
# jedem Test-Upload mitgefuehrt, damit er durch den Import nicht sich selbst
# deaktiviert.
ADMIN_ROW = "T-ADMIN;Anna;Admin;;Testabteilung;IT;;;1"


def _upload_csv(client, headers, path, *rows):
    content = "\n".join([CSV_HEADER, ADMIN_ROW, *rows])
    files = {"file": ("org.csv", io.BytesIO(content.encode("utf-8")), "text/csv")}
    return client.post(path, headers=headers, files=files)


def test_non_admin_cannot_access_organisation_routes(client, seeded_users):
    headers = _auth_headers(client, "T-MA")
    response = client.get("/organisation/persons", headers=headers)
    assert response.status_code == 403


def test_import_dry_run_then_apply(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")

    dry_run = _upload_csv(
        client, headers, "/organisation/import/dry-run",
        "P100;Neu;Person;neu@example.test;IT;IT;;;1",
    )
    assert dry_run.status_code == 200
    body = dry_run.json()
    assert body["new"][0]["personalnummer"] == "P100"

    # Trockenlauf darf nichts geschrieben haben
    persons_after_dry_run = client.get("/organisation/persons?q=P100", headers=headers).json()
    assert persons_after_dry_run["total"] == 0

    apply_response = _upload_csv(
        client, headers, "/organisation/import/apply",
        "P100;Neu;Person;neu@example.test;IT;IT;;;1",
    )
    assert apply_response.status_code == 200

    persons_after_apply = client.get("/organisation/persons?q=P100", headers=headers).json()
    assert persons_after_apply["total"] == 1
    assert "mitarbeiter" in persons_after_apply["items"][0]["roles"]


def test_import_apply_derives_fuehrungskraft_role(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    _upload_csv(
        client, headers, "/organisation/import/apply",
        "P200;Chef;Chefin;chef@example.test;IT;IT;;;1",
        "P201;Team;Mitglied;team@example.test;IT;IT;P200;;1",
    )

    persons = client.get("/organisation/persons?q=P200", headers=headers).json()["items"]
    assert "fuehrungskraft" in persons[0]["roles"]


def test_person_detail_includes_org_path_and_team_size(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    _upload_csv(
        client, headers, "/organisation/import/apply",
        "P300;Ober;Chef;;IT;IT;;;1",
        "P301;Mittel;Chef;;IT;IT;P300;;1",
        "P302;Team;Mitglied;;IT;IT;P301;;1",
    )
    persons = client.get("/organisation/persons?q=P302", headers=headers).json()["items"]
    person_id = persons[0]["id"]

    detail = client.get(f"/organisation/persons/{person_id}", headers=headers).json()
    assert [p["personalnummer"] for p in detail["org_path"]] == ["P300", "P301"]
    assert detail["team_size"] == 0


def test_deactivate_person_revokes_derived_roles(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    _upload_csv(
        client, headers, "/organisation/import/apply",
        "P400;Chef;Chefin;;IT;IT;;;1",
        "P401;Team;Mitglied;;IT;IT;P400;;1",
    )
    leader = client.get("/organisation/persons?q=P400", headers=headers).json()["items"][0]
    assert "fuehrungskraft" in leader["roles"]

    member = client.get("/organisation/persons?q=P401", headers=headers).json()["items"][0]
    client.post(f"/organisation/persons/{member['id']}/deactivate", headers=headers)

    leader_after = client.get(f"/organisation/persons/{leader['id']}", headers=headers).json()
    assert "fuehrungskraft" not in leader_after["roles"]


def test_org_tree_marks_small_teams(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    _upload_csv(
        client, headers, "/organisation/import/apply",
        "P500;Chef;Klein;;IT;IT;;;1",
        "P501;Team;Eins;;IT;IT;P500;;1",
    )
    tree = client.get("/organisation/tree", headers=headers).json()
    node = next(n for n in tree if n["personalnummer"] == "P500")
    assert node["team_size"] == 1
    assert node["team_too_small"] is True


def test_set_admin_role_toggle(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    _upload_csv(client, headers, "/organisation/import/apply", "P600;Neu;Admin;;IT;IT;;;1")
    person = client.get("/organisation/persons?q=P600", headers=headers).json()["items"][0]

    response = client.post(
        f"/organisation/persons/{person['id']}/admin-role", headers=headers, json={"is_admin": True}
    )
    assert "admin" in response.json()["roles"]

    response = client.post(
        f"/organisation/persons/{person['id']}/admin-role", headers=headers, json={"is_admin": False}
    )
    assert "admin" not in response.json()["roles"]


def test_import_schedule_defaults_disabled_and_can_be_updated(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")

    default = client.get("/organisation/import/schedule", headers=headers).json()
    assert default["enabled"] is False

    updated = client.put(
        "/organisation/import/schedule",
        headers=headers,
        json={"enabled": True, "cron": "30 3 * * *", "csv_path": "/data/org-import/latest.csv"},
    ).json()
    assert updated == {"enabled": True, "cron": "30 3 * * *", "csv_path": "/data/org-import/latest.csv"}

    persisted = client.get("/organisation/import/schedule", headers=headers).json()
    assert persisted == updated
