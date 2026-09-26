import csv
import io

from app.models.survey import SurveyVersion
from app.services.survey_export import build_tsv


def _h(client, pnr):
    return {"Authorization": "Bearer " + client.post("/auth/dev-login", json={"personalnummer": pnr}).json()["access_token"]}


def _survey(client, h):
    client.post("/surveys/templates", json={"name": "ML"}, headers=h)
    vid = client.get("/surveys/templates", headers=h).json()[0]["versions"][0]["id"]
    did = client.post(f"/surveys/versions/{vid}/dimensions", json={"name": "Kommunikation"}, headers=h).json()["id"]
    q1 = client.post(f"/surveys/versions/{vid}/questions", headers=h, json={
        "type": "likert", "text": "Klar kommuniziert?", "dimension_id": did, "scale_min": 1, "scale_max": 5,
        "scale_labels": ["nie", "selten", "manchmal", "oft", "immer"], "help_text": "Bitte ehrlich"}).json()["id"]
    q2 = client.post(f"/surveys/versions/{vid}/questions", headers=h, json={
        "type": "choice", "text": "Themen?", "dimension_id": did, "options": ["Lob", "Kritik"], "allow_multiple": True}).json()["id"]
    return vid, did, q1, q2


def _rows(tsv):
    return list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))


def test_multilanguage_export_blocks_fallback_and_order(client, seeded_users, db_session):
    h = _h(client, "T-ADMIN")
    vid, did, q1, q2 = _survey(client, h)
    assert client.put(f"/surveys/versions/{vid}/languages", json={"languages": ["en", "de", "en"]}, headers=h).json()["languages"] == ["en"]
    assert client.put(f"/surveys/versions/{vid}/languages", json={"languages": ["xx"]}, headers=h).status_code == 400

    r = client.put(f"/surveys/questions/{q1}/translations/en", headers=h, json={
        "text": "Communicates clearly?", "scale_labels": ["never", "rarely", "sometimes", "often", "always"]})
    assert r.status_code == 200
    assert client.put(f"/surveys/questions/{q1}/translations/en", headers=h, json={"scale_labels": ["a", "b"]}).status_code == 400
    assert client.put(f"/surveys/questions/{q2}/translations/en", headers=h, json={"options": ["Praise"]}).status_code == 400  # falsche Laenge
    assert client.put(f"/surveys/dimensions/{did}/translations/en", headers=h, json={"name": "Communication"}).status_code == 200

    rows = _rows(build_tsv(db_session.get(SurveyVersion, vid)))
    assert any(r["class"] == "S" and r["name"] == "additional_languages" and r["text"] == "en" for r in rows)
    de = [r for r in rows if r["language"] == "de" and r["class"] in ("G", "Q", "A", "SQ")]
    en = [r for r in rows if r["language"] == "en" and r["class"] in ("G", "Q", "A", "SQ")]
    # gleiche Struktur/Reihenfolge und gleiche Codes je Sprache (Voraussetzung fuer den LimeSurvey-Import)
    assert [(r["class"], r["name"]) for r in de if r["class"] != "G"] == [(r["class"], r["name"]) for r in en if r["class"] != "G"]
    assert len([r for r in de if r["class"] == "G"]) == len([r for r in en if r["class"] == "G"]) == 1
    assert [r["name"] for r in en if r["class"] == "G"] == ["Communication"]
    q1_en = next(r for r in en if r["class"] == "Q" and r["name"] == f"Q{q1}")
    assert q1_en["text"] == "Communicates clearly?" and q1_en["help"] == "Bitte ehrlich"  # Hilfetext faellt auf Deutsch zurueck
    assert [r["text"] for r in en if r["class"] == "A"] == ["never", "rarely", "sometimes", "often", "always"]
    assert [r["text"] for r in en if r["class"] == "SQ"] == ["Lob", "Kritik"]  # Optionen ohne Uebersetzung -> Deutsch
    assert {r["language"] for r in rows if r["class"] == "SL"} == {"de", "en"}


def test_single_language_export_unchanged(client, seeded_users, db_session):
    h = _h(client, "T-ADMIN")
    vid, *_ = _survey(client, h)
    rows = _rows(build_tsv(db_session.get(SurveyVersion, vid)))
    assert {r["language"] for r in rows if r["language"]} == {"de"}
    assert not any(r["name"] == "additional_languages" for r in rows)


def test_translation_needs_permission_and_editable_version(client, seeded_users):
    h = _h(client, "T-ADMIN")
    vid, did, q1, _ = _survey(client, h)
    hm = _h(client, "T-MA")
    assert client.put(f"/surveys/versions/{vid}/languages", json={"languages": ["en"]}, headers=hm).status_code == 403
    assert client.post(f"/surveys/versions/{vid}/translate?lang=en", headers=h).status_code == 409  # kein KI-Provider


def test_user_language_preference_and_available_languages(client, seeded_users):
    h = _h(client, "T-ADMIN")
    vid, *_ = _survey(client, h)
    client.put(f"/surveys/versions/{vid}/languages", json={"languages": ["tr"]}, headers=h)
    hm = _h(client, "T-MA")
    info = client.get("/languages", headers=hm).json()
    assert {c["code"] for c in info["available"]} == {"de", "tr"} and info["mine"] == "de"
    assert client.put("/auth/me/language", json={"language": "tr"}, headers=hm).json()["language"] == "tr"
    assert client.put("/auth/me/language", json={"language": "klingon"}, headers=hm).status_code == 400
    assert client.get("/auth/me", headers=hm).json()["language"] == "tr"
    assert client.get("/languages").status_code == 401
