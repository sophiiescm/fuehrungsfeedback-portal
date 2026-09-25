from datetime import datetime, timezone

from app.models.round import Round, RoundStatus


def _auth_headers(client, personalnummer: str) -> dict:
    response = client.post("/auth/dev-login", json={"personalnummer": personalnummer})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_template_creates_initial_draft_version(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    response = client.post("/surveys/templates", headers=headers, json={"name": "Führungsfeedback Standard"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["versions"]) == 1
    assert body["versions"][0]["status"] == "entwurf"


def test_add_dimension_and_question_then_reorder(client, seeded_users):
    headers = _auth_headers(client, "T-ADMIN")
    template = client.post("/surveys/templates", headers=headers, json={"name": "Test"}).json()
    version_id = template["versions"][0]["id"]

    dim = client.post(
        f"/surveys/versions/{version_id}/dimensions", headers=headers, json={"name": "Kommunikation"}
    ).json()
    q1 = client.post(
        f"/surveys/versions/{version_id}/questions", headers=headers,
        json={"type": "likert", "text": "Frage A", "dimension_id": dim["id"]},
    ).json()
    q2 = client.post(
        f"/surveys/versions/{version_id}/questions", headers=headers,
        json={"type": "freitext", "text": "Frage B", "mandatory": False},
    ).json()

    detail = client.get(f"/surveys/versions/{version_id}", headers=headers).json()
    assert [q["id"] for q in detail["questions"]] == [q1["id"], q2["id"]]

    reordered = client.put(
        f"/surveys/versions/{version_id}/reorder", headers=headers,
        json={"questions": [
            {"id": q2["id"], "dimension_id": None, "sort_order": 1},
            {"id": q1["id"], "dimension_id": dim["id"], "sort_order": 2},
        ]},
    ).json()
    assert [q["id"] for q in reordered["questions"]] == [q2["id"], q1["id"]]


def test_editing_locked_version_returns_409(client, seeded_users, db_session):
    headers = _auth_headers(client, "T-ADMIN")
    template = client.post("/surveys/templates", headers=headers, json={"name": "Gesperrt"}).json()
    version_id = template["versions"][0]["id"]

    round_ = Round(
        name="Runde", survey_version_id=version_id, status=RoundStatus.geplant,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db_session.add(round_)
    db_session.commit()

    response = client.post(
        f"/surveys/versions/{version_id}/dimensions", headers=headers, json={"name": "Neu"}
    )
    assert response.status_code == 409


def test_clone_locked_version_produces_editable_draft(client, seeded_users, db_session):
    headers = _auth_headers(client, "T-ADMIN")
    template = client.post("/surveys/templates", headers=headers, json={"name": "Original"}).json()
    version_id = template["versions"][0]["id"]
    client.post(f"/surveys/versions/{version_id}/dimensions", headers=headers, json={"name": "Kommunikation"})

    round_ = Round(
        name="Runde", survey_version_id=version_id, status=RoundStatus.geplant,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc), end_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    db_session.add(round_)
    db_session.commit()

    clone_response = client.post(f"/surveys/versions/{version_id}/clone", headers=headers)
    assert clone_response.status_code == 200
    clone = clone_response.json()
    assert clone["version_number"] == 2
    assert clone["status"] == "entwurf"
    assert len(clone["dimensions"]) == 1

    add_response = client.post(
        f"/surveys/versions/{clone['id']}/dimensions", headers=headers, json={"name": "Weitere Dimension"}
    )
    assert add_response.status_code == 200


def test_transfer_to_limesurvey_uses_client_and_stores_sid(client, seeded_users, monkeypatch):
    headers = _auth_headers(client, "T-ADMIN")
    template = client.post("/surveys/templates", headers=headers, json={"name": "Transfer-Test"}).json()
    version_id = template["versions"][0]["id"]
    client.post(
        f"/surveys/versions/{version_id}/questions", headers=headers,
        json={"type": "freitext", "text": "Frage", "mandatory": False},
    )

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def import_survey(self, data_b64, import_type, survey_name):
            assert import_type == "txt"
            return 999999

        def delete_survey(self, sid):
            raise AssertionError("sollte beim ersten Transfer nicht aufgerufen werden")

        def close(self):
            pass

    import app.api.routes.surveys as surveys_module

    monkeypatch.setattr(surveys_module, "LimeSurveyClient", FakeClient)

    response = client.post(f"/surveys/versions/{version_id}/transfer", headers=headers)
    assert response.status_code == 200
    assert response.json()["limesurvey_template_sid"] == 999999

    detail = client.get(f"/surveys/versions/{version_id}", headers=headers).json()
    assert detail["limesurvey_template_sid"] == 999999
