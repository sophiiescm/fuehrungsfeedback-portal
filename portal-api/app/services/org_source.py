"""Adapter-Interface fuer die Anbindung von Organisationsdaten (CLAUDE.md: "SAP-Schnittstelle").

`CsvOrgSource` ist die aktuell genutzte Implementierung. `ODataOrgSource` ist
ein vorbereiteter Stub fuer SuccessFactors/SAP HCM (siehe OPEN_QUESTIONS.md:
welches SAP-System liefert die Org-Daten ist noch offen -> Annahme CSV-Export).
"""

from __future__ import annotations

import csv
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OrgRecord:
    personalnummer: str
    vorname: str
    nachname: str
    email: str | None
    org_einheit: str
    fachbereich: str
    manager_personalnummer: str | None
    standort: str | None
    aktiv: bool


class OrgSourceError(RuntimeError):
    pass


class OrgSource(ABC):
    @abstractmethod
    def fetch(self) -> list[OrgRecord]:
        """Liefert den vollstaendigen aktuellen Organisationsstand."""


CSV_COLUMNS = [
    "personalnummer",
    "vorname",
    "nachname",
    "email",
    "org_einheit",
    "fachbereich",
    "manager_personalnummer",
    "standort",
    "aktiv",
]


class CsvOrgSource(OrgSource):
    """CLAUDE.md CSV-Format (UTF-8, Semikolon):
    personalnummer;vorname;nachname;email;org_einheit;fachbereich;manager_personalnummer;standort;aktiv
    """

    def __init__(self, content: str):
        self._content = content

    def fetch(self) -> list[OrgRecord]:
        reader = csv.DictReader(io.StringIO(self._content), delimiter=";")
        missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise OrgSourceError(f"CSV fehlen Spalten: {', '.join(sorted(missing))}")

        records: list[OrgRecord] = []
        for line_no, row in enumerate(reader, start=2):
            personalnummer = row["personalnummer"].strip()
            if not personalnummer:
                raise OrgSourceError(f"Zeile {line_no}: personalnummer fehlt")
            manager = row["manager_personalnummer"].strip() or None
            email = row["email"].strip() or None
            aktiv_raw = row["aktiv"].strip().lower()
            records.append(
                OrgRecord(
                    personalnummer=personalnummer,
                    vorname=row["vorname"].strip(),
                    nachname=row["nachname"].strip(),
                    email=email,
                    org_einheit=row["org_einheit"].strip(),
                    fachbereich=row["fachbereich"].strip(),
                    manager_personalnummer=manager if manager != personalnummer else None,
                    standort=row["standort"].strip() or None,
                    aktiv=aktiv_raw in {"1", "true", "ja", "j", "y"},
                )
            )
        return records


class ODataOrgSource(OrgSource):
    """SuccessFactors (OData v2) -- Entitaet `User` mit `manager`-Beziehung.

    Standard-Feldzuordnung (per `field_map` anpassbar, da Tenants abweichen koennen):
      userId -> personalnummer, firstName, lastName, email, department -> org_einheit,
      division -> fachbereich, location -> standort, manager/userId -> Vorgesetzter,
      status ('active'/'t' ...) -> aktiv. Paging ueber $top/$skip, Basic-Auth.
    """

    DEFAULT_MAP = {
        "personalnummer": "userId", "vorname": "firstName", "nachname": "lastName", "email": "email",
        "org_einheit": "department", "fachbereich": "division", "standort": "location", "status": "status",
    }
    ACTIVE = {"active", "t", "a", "true", "1"}

    def __init__(self, base_url: str, user: str | None = None, password: str | None = None,
                 field_map: dict[str, str] | None = None, page_size: int = 200, client=None):
        self._base_url = base_url.rstrip("/")
        self._auth = (user, password) if user else None
        self._map = {**self.DEFAULT_MAP, **(field_map or {})}
        self._page = page_size
        self._client = client  # fuer Tests (httpx-Client mit MockTransport)

    def _get(self, url: str, params: dict) -> dict:
        import httpx

        client = self._client or httpx.Client(timeout=30)
        try:
            r = client.get(url, params=params, auth=self._auth, headers={"Accept": "application/json"})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise OrgSourceError(f"OData-Abruf fehlgeschlagen: {exc}") from exc

    def fetch(self) -> list[OrgRecord]:
        m = self._map
        select_fields = ",".join(m.values()) + ",manager/userId"
        records: list[OrgRecord] = []
        skip = 0
        while True:
            data = self._get(f"{self._base_url}/User", {
                "$format": "json", "$select": select_fields, "$expand": "manager",
                "$top": self._page, "$skip": skip,
            })
            d = data.get("d", data)
            rows = d.get("results", d.get("value", []))
            for row in rows:
                pnr = str(row.get(m["personalnummer"]) or "").strip()
                if not pnr:
                    raise OrgSourceError("OData: Datensatz ohne Personalnummer")
                mgr = row.get("manager") or {}
                mgr_id = str(mgr.get("userId") or "").strip() or None
                records.append(OrgRecord(
                    personalnummer=pnr,
                    vorname=(row.get(m["vorname"]) or "").strip(),
                    nachname=(row.get(m["nachname"]) or "").strip(),
                    email=(row.get(m["email"]) or "").strip() or None,
                    org_einheit=(row.get(m["org_einheit"]) or "").strip(),
                    fachbereich=(row.get(m["fachbereich"]) or "").strip(),
                    manager_personalnummer=mgr_id if mgr_id != pnr else None,
                    standort=(row.get(m["standort"]) or "").strip() or None,
                    aktiv=str(row.get(m["status"], "active")).strip().lower() in self.ACTIVE,
                ))
            if len(rows) < self._page:
                return records
            skip += self._page
