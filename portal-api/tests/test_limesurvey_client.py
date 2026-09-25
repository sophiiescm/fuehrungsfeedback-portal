import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError

RC_URL = "http://limesurvey.test/index.php/admin/remotecontrol"


def _settings() -> Settings:
    return Settings(limesurvey_rc_api_url=RC_URL, limesurvey_rc_user="admin", limesurvey_rc_password="secret")


@respx.mock
def test_authenticates_lazily_on_first_call():
    calls = []

    def _responder(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        calls.append(payload["method"])
        if payload["method"] == "get_session_key":
            return httpx.Response(200, json={"id": payload["id"], "result": "sess-123", "error": None})
        if payload["method"] == "list_surveys":
            assert payload["params"][0] == "sess-123"
            return httpx.Response(200, json={"id": payload["id"], "result": [{"sid": 1}], "error": None})
        raise AssertionError(f"unerwarteter Methodenaufruf {payload['method']}")

    respx.post(RC_URL).mock(side_effect=_responder)

    client = LimeSurveyClient(settings=_settings())
    surveys = client.list_surveys()

    assert surveys == [{"sid": 1}]
    assert calls == ["get_session_key", "list_surveys"]


@respx.mock
def test_copy_survey_returns_new_sid():
    def _responder(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        if payload["method"] == "get_session_key":
            return httpx.Response(200, json={"id": payload["id"], "result": "sess-abc", "error": None})
        if payload["method"] == "copy_survey":
            return httpx.Response(
                200, json={"id": payload["id"], "result": {"status": "OK", "newsid": 999}, "error": None}
            )
        raise AssertionError(payload["method"])

    respx.post(RC_URL).mock(side_effect=_responder)

    client = LimeSurveyClient(settings=_settings())
    new_sid = client.copy_survey(1, "Runde 1 - FK-A0001")

    assert new_sid == 999


@respx.mock
def test_add_participants_without_activate_tokens_raises_domain_error():
    """Regressionstest fuer den Phase-0-Befund: add_participants schlaegt fehl,
    wenn activate_tokens fuer diese Umfrage nie aufgerufen wurde."""

    def _responder(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        if payload["method"] == "get_session_key":
            return httpx.Response(200, json={"id": payload["id"], "result": "sess-abc", "error": None})
        if payload["method"] == "add_participants":
            return httpx.Response(
                200, json={"id": payload["id"], "result": {"status": "No survey participant list"}, "error": None}
            )
        raise AssertionError(payload["method"])

    respx.post(RC_URL).mock(side_effect=_responder)

    client = LimeSurveyClient(settings=_settings())
    with pytest.raises(LimeSurveyError, match="add_participants fehlgeschlagen"):
        client.add_participants(1, [{"email": "a@example.test"}])


@respx.mock
def test_reauthenticates_on_invalid_session_key():
    session_keys_issued = []

    def _responder(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        if payload["method"] == "get_session_key":
            new_key = f"sess-{len(session_keys_issued) + 1}"
            session_keys_issued.append(new_key)
            return httpx.Response(200, json={"id": payload["id"], "result": new_key, "error": None})
        if payload["method"] == "list_surveys":
            used_key = payload["params"][0]
            if used_key == "sess-1":
                return httpx.Response(
                    200, json={"id": payload["id"], "result": {"status": "Invalid session key"}, "error": None}
                )
            return httpx.Response(200, json={"id": payload["id"], "result": [{"sid": 42}], "error": None})
        raise AssertionError(payload["method"])

    respx.post(RC_URL).mock(side_effect=_responder)

    client = LimeSurveyClient(settings=_settings())
    result = client.list_surveys()

    assert result == [{"sid": 42}]
    assert session_keys_issued == ["sess-1", "sess-2"]


@respx.mock
def test_raw_jsonrpc_error_raises():
    def _responder(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        if payload["method"] == "get_session_key":
            return httpx.Response(200, json={"id": payload["id"], "result": None, "error": "Invalid user name or password"})
        raise AssertionError(payload["method"])

    respx.post(RC_URL).mock(side_effect=_responder)

    client = LimeSurveyClient(settings=_settings())
    with pytest.raises(LimeSurveyError):
        client.list_surveys()


@respx.mock
def test_transport_error_retries_then_raises():
    respx.post(RC_URL).mock(side_effect=httpx.ConnectError("boom"))

    client = LimeSurveyClient(settings=_settings())
    with pytest.raises(LimeSurveyError, match="fehlgeschlagen nach 3 Versuchen"):
        client.list_surveys()
