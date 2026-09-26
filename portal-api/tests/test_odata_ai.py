import json

import httpx
import pytest

from app.core.config import get_settings
from app.services import ai, textanalysis
from app.services.org_source import ODataOrgSource, OrgSourceError


def _client(rows_by_skip, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        assert request.url.params["$expand"] == "manager"
        skip = int(request.url.params["$skip"])
        return httpx.Response(status, json={"d": {"results": rows_by_skip.get(skip, [])}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _row(i, mgr=None, status="active"):
    return {"userId": f"P{i}", "firstName": "V", "lastName": f"N{i}", "email": f"p{i}@example.test",
            "department": "Abt", "division": "IT", "location": "Ort", "status": status,
            "manager": {"userId": mgr} if mgr else None}


def test_odata_paging_and_mapping():
    src = ODataOrgSource("https://sf.example.test/odata/v2", "u", "p", page_size=2,
                         client=_client({0: [_row(1), _row(2, "P1")], 2: [_row(3, "P1", "inactive")]}))
    recs = src.fetch()
    assert [r.personalnummer for r in recs] == ["P1", "P2", "P3"]
    assert recs[1].manager_personalnummer == "P1" and recs[0].manager_personalnummer is None
    assert recs[2].aktiv is False and recs[0].fachbereich == "IT"


def test_odata_error_is_wrapped():
    with pytest.raises(OrgSourceError):
        ODataOrgSource("https://sf.example.test", "u", "p", client=_client({}, status=500)).fetch()


def test_ai_categorize_validates_output(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ai_provider", "openai_compatible")
    texts = ["Mehr Feedback bitte", "Faire Verteilung", "Bla"]
    monkeypatch.setattr(ai, "_chat", lambda p, max_tokens=600: '["Kommunikation", "ERFUNDEN", "Sonstiges"]')
    out = ai.categorize(texts)
    assert out["Mehr Feedback bitte"] == "Kommunikation"
    assert out["Faire Verteilung"] == textanalysis.categorize_keywords(texts)["Faire Verteilung"]  # ungueltig -> Fallback
    monkeypatch.setattr(ai, "_chat", lambda p, max_tokens=600: None)
    assert ai.categorize(texts) == textanalysis.categorize_keywords(texts)
