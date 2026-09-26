"""JSON-RPC-Wrapper fuer die LimeSurvey RemoteControl-2-API.

Erkenntnisse aus der Phase-0-Analyse (docs/limesurvey-analyse.md) die hier
beruecksichtigt sind:
- Es gibt keine RPC-Methode zum Anlegen eingeschraenkter Admin-User; der
  konfigurierte technische User (ADMIN_* aus dem Docker-Image) wird direkt
  verwendet (docs/ENTSCHEIDUNGEN.md Nr. 8).
- `add_participants` schlaegt mit {"status": "No survey participant list"}
  fehl, wenn `activate_tokens` fuer diese Umfrage noch nie aufgerufen wurde.
- `copy_survey` ist der gewaehlte Weg, um pro Runde+Fuehrungskraft eine eigene
  Umfrage aus der Vorlage zu erzeugen (docs/ENTSCHEIDUNGEN.md Nr. 9).
"""

from __future__ import annotations

import itertools
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class LimeSurveyError(RuntimeError):
    """Fehler auf JSON-RPC-Ebene (das 'error'-Feld der Antwort war gesetzt)."""


class LimeSurveyClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        self._settings = settings or get_settings()
        self._client = httpx.Client(transport=transport, timeout=15.0)
        self._session_key: str | None = None
        self._id_counter = itertools.count(1)

    def close(self) -> None:
        if self._session_key is not None:
            try:
                self._raw_call("release_session_key", [self._session_key])
            except Exception:
                pass
            self._session_key = None
        self._client.close()

    def __enter__(self) -> "LimeSurveyClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Session-Handling -------------------------------------------------

    def _authenticate(self) -> str:
        result = self._raw_call(
            "get_session_key",
            [self._settings.limesurvey_rc_user, self._settings.limesurvey_rc_password],
        )
        if not isinstance(result, str):
            raise LimeSurveyError(f"Anmeldung fehlgeschlagen: {result!r}")
        self._session_key = result
        return result

    def _raw_call(self, method: str, params: list[Any], retries: int = 3) -> Any:
        payload = {"method": method, "params": params, "id": next(self._id_counter)}
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._client.post(self._settings.limesurvey_rc_api_url, json=payload)
                response.raise_for_status()
                data = response.json()
                if data.get("error"):
                    raise LimeSurveyError(str(data["error"]))
                return data["result"]
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                continue
        raise LimeSurveyError(f"RemoteControl-Aufruf '{method}' fehlgeschlagen nach {retries} Versuchen") from last_exc

    def call(self, method: str, *params: Any) -> Any:
        """Ruft eine authentifizierte RPC-Methode auf (Session-Key wird automatisch vorangestellt)."""
        if self._session_key is None:
            self._authenticate()

        result = self._raw_call(method, [self._session_key, *params])

        if isinstance(result, dict) and result.get("status") in {
            "Invalid session key",
            "Invalid Session Key",
        }:
            self._authenticate()
            result = self._raw_call(method, [self._session_key, *params])

        return result

    # -- Komfortmethoden fuer die im Projekt benoetigten RC-Aufrufe --------

    def list_surveys(self) -> list[dict]:
        result = self.call("list_surveys")
        return result if isinstance(result, list) else []

    def copy_survey(self, source_sid: int, new_name: str) -> int:
        result = self.call("copy_survey", source_sid, new_name)
        if not isinstance(result, dict) or result.get("status") != "OK":
            raise LimeSurveyError(f"copy_survey fehlgeschlagen: {result!r}")
        return int(result["newsid"])

    def delete_survey(self, sid: int) -> None:
        result = self.call("delete_survey", sid)
        if not isinstance(result, dict) or result.get("status") != "OK":
            raise LimeSurveyError(f"delete_survey fehlgeschlagen: {result!r}")

    def activate_survey(self, sid: int) -> dict:
        return self.call("activate_survey", sid)

    def activate_tokens(self, sid: int, attribute_fields: list[int] | None = None) -> None:
        result = self.call("activate_tokens", sid, attribute_fields or [])
        if not isinstance(result, dict) or result.get("status") != "OK":
            raise LimeSurveyError(f"activate_tokens fehlgeschlagen: {result!r}")

    def add_participants(self, sid: int, participants: list[dict]) -> list[dict]:
        result = self.call("add_participants", sid, participants, True)
        if not isinstance(result, list):
            raise LimeSurveyError(f"add_participants fehlgeschlagen: {result!r}")
        return result

    def list_participants(self, sid: int, start: int = 0, limit: int = 1000) -> list[dict]:
        result = self.call("list_participants", sid, start, limit, False, ["completed"])
        return result if isinstance(result, list) else []

    def get_summary(self, sid: int) -> dict:
        result = self.call("get_summary", sid)
        return result if isinstance(result, dict) else {}

    def export_responses(self, sid: int, response_type: str = "short") -> bytes | None:
        """Antwortcodes ("short"), nicht Antworttexte. Gibt die base64-dekodierten Rohdaten zurueck, oder None wenn es keine Antworten gibt."""
        result = self.call("export_responses", sid, "json", None, "complete", "code", response_type)
        if isinstance(result, dict) and "status" in result:
            return None
        if isinstance(result, str):
            import base64

            return base64.b64decode(result)
        return None

    def import_survey(self, data_base64: str, import_type: str = "lss", survey_name: str | None = None) -> int:
        """`import_type` ist eine der von LimeSurvey akzeptierten Erweiterungen:
        'lss' (XML), 'txt' (TSV, siehe app.services.survey_export), 'csv' oder 'lsa'."""
        params: list[Any] = [data_base64, import_type]
        if survey_name:
            params.append(survey_name)
        result = self.call("import_survey", *params)
        if not isinstance(result, int):
            raise LimeSurveyError(f"import_survey fehlgeschlagen: {result!r}")
        return result
