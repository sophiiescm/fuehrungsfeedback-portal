from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FieldChangeOut(BaseModel):
    field: str
    old: object
    new: object


class ChangedPersonOut(BaseModel):
    personalnummer: str
    changes: list[FieldChangeOut]


class NewPersonOut(BaseModel):
    personalnummer: str
    vorname: str
    nachname: str
    org_einheit: str
    fachbereich: str


class ImportDiffOut(BaseModel):
    new: list[NewPersonOut]
    changed: list[ChangedPersonOut]
    deactivated: list[str]
    unchanged_count: int
    issues: list[str]


class ImportLogOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    dry_run: bool
    status: str
    triggered_by: str
    summary: dict | None

    model_config = ConfigDict(from_attributes=True)


class PersonListItemOut(BaseModel):
    id: int
    personalnummer: str
    full_name: str
    email: str | None
    fachbereich: str | None
    org_einheit: str | None
    roles: list[str]
    aktiv: bool


class PersonListOut(BaseModel):
    items: list[PersonListItemOut]
    total: int


class OrgPathEntryOut(BaseModel):
    personalnummer: str
    full_name: str


class PersonDetailOut(BaseModel):
    id: int
    personalnummer: str
    vorname: str
    nachname: str
    email: str | None
    fachbereich: str | None
    org_einheit: str | None
    standort: str | None
    aktiv: bool
    roles: list[str]
    team_size: int
    org_path: list[OrgPathEntryOut]


class SetAdminRoleIn(BaseModel):
    is_admin: bool


class ImportScheduleOut(BaseModel):
    enabled: bool
    cron: str
    csv_path: str | None


class ImportScheduleIn(BaseModel):
    enabled: bool
    cron: str = "0 2 * * *"
    csv_path: str | None = None


class OrgTreeNodeOut(BaseModel):
    personalnummer: str
    full_name: str
    fachbereich: str | None
    team_size: int
    team_too_small: bool
    children: list["OrgTreeNodeOut"]
