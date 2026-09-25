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
    """Stub fuer SuccessFactors/SAP HCM. Noch nicht implementiert.

    Wenn ein konkretes Zielsystem feststeht (siehe OPEN_QUESTIONS.md), hier
    die OData-Abfrage ergaenzen und in `OrgRecord`-Objekte uebersetzen. Die
    Diff-/Plausibilitaets-/Rollenlogik in org_import.py bleibt unveraendert,
    da sie nur gegen das `OrgSource`-Interface arbeitet.
    """

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def fetch(self) -> list[OrgRecord]:
        raise NotImplementedError(
            "ODataOrgSource ist ein vorbereiteter Stub. Siehe OPEN_QUESTIONS.md "
            "(SAP-System noch nicht festgelegt)."
        )
