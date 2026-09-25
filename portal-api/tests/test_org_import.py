import pytest

from app.models.person import OrgUnit, Person, Role, RoleAssignment
from app.services.org_import import apply_import, check_plausibility, compute_diff
from app.services.org_source import CsvOrgSource, OrgSourceError

CSV_HEADER = "personalnummer;vorname;nachname;email;org_einheit;fachbereich;manager_personalnummer;standort;aktiv"


def make_csv(*rows: str) -> str:
    return "\n".join([CSV_HEADER, *rows])


def test_csv_org_source_parses_valid_rows():
    csv_content = make_csv(
        "P001;Anna;Admin;anna@example.test;IT;IT;;Berlin;1",
        "P002;Frank;FK;frank@example.test;IT;IT;P001;Berlin;1",
    )
    records = CsvOrgSource(csv_content).fetch()
    assert len(records) == 2
    assert records[1].manager_personalnummer == "P001"
    assert records[0].manager_personalnummer is None
    assert records[0].aktiv is True


def test_csv_org_source_missing_column_raises():
    with pytest.raises(OrgSourceError, match="fehlen Spalten"):
        CsvOrgSource("personalnummer;vorname\nP001;Anna").fetch()


def test_csv_org_source_missing_personalnummer_raises():
    csv_content = make_csv(";Anna;Admin;;IT;IT;;;1")
    with pytest.raises(OrgSourceError, match="personalnummer fehlt"):
        CsvOrgSource(csv_content).fetch()


def test_check_plausibility_detects_duplicate():
    csv_content = make_csv(
        "P001;Anna;Admin;;IT;IT;;;1",
        "P001;Anna;Zweite;;IT;IT;;;1",
    )
    records = CsvOrgSource(csv_content).fetch()
    issues = check_plausibility(records)
    assert any("Doppelte Personalnummer" in i and "P001" in i for i in issues)


def test_check_plausibility_detects_missing_manager():
    csv_content = make_csv("P002;Frank;FK;;IT;IT;P999;;1")
    records = CsvOrgSource(csv_content).fetch()
    issues = check_plausibility(records)
    assert any("P999" in i for i in issues)


def test_check_plausibility_detects_cycle():
    csv_content = make_csv(
        "P001;A;A;;IT;IT;P002;;1",
        "P002;B;B;;IT;IT;P001;;1",
    )
    records = CsvOrgSource(csv_content).fetch()
    issues = check_plausibility(records)
    assert any("Zyklus" in i for i in issues)


def test_compute_diff_classifies_new_changed_unchanged_deactivated(db_session):
    org_unit = OrgUnit(name="IT", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()
    existing_unchanged = Person(
        personalnummer="P001", vorname="Anna", nachname="Admin", org_unit_id=org_unit.id,
        email=None, standort=None, aktiv=True,
    )
    existing_to_change = Person(
        personalnummer="P002", vorname="Frank", nachname="Alt", org_unit_id=org_unit.id,
        email=None, standort=None, aktiv=True,
    )
    existing_to_deactivate = Person(
        personalnummer="P003", vorname="Mia", nachname="MA", org_unit_id=org_unit.id,
        email=None, standort=None, aktiv=True,
    )
    db_session.add_all([existing_unchanged, existing_to_change, existing_to_deactivate])
    db_session.commit()

    csv_content = make_csv(
        "P001;Anna;Admin;;IT;IT;;;1",  # unveraendert
        "P002;Frank;Neu;;IT;IT;;;1",  # nachname geaendert
        "P004;Neu;Person;;IT;IT;;;1",  # neu
        # P003 fehlt -> deaktiviert
    )
    records = CsvOrgSource(csv_content).fetch()
    diff = compute_diff(db_session, records)

    assert diff.unchanged_count == 1
    assert [c.personalnummer for c in diff.changed] == ["P002"]
    assert diff.changed[0].changes[0].field == "nachname"
    assert [r.personalnummer for r in diff.new] == ["P004"]
    assert diff.deactivated == ["P003"]


def test_apply_import_writes_persons_and_deactivates(db_session):
    csv_content = make_csv(
        "P001;Anna;Admin;anna@example.test;IT;IT;;Berlin;1",
        "P002;Frank;FK;frank@example.test;IT;IT;P001;Berlin;1",
    )
    records = CsvOrgSource(csv_content).fetch()
    apply_import(db_session, records, triggered_by="test")

    persons = {p.personalnummer: p for p in db_session.query(Person).all()}
    assert set(persons) == {"P001", "P002"}
    assert persons["P002"].manager_personalnummer == "P001"
    assert persons["P001"].org_unit.fachbereich == "IT"

    # Zweiter Import ohne P002 -> deaktiviert, P001 bleibt aktiv
    second_csv = make_csv("P001;Anna;Admin;anna@example.test;IT;IT;;Berlin;1")
    apply_import(db_session, CsvOrgSource(second_csv).fetch(), triggered_by="test")
    db_session.expire_all()
    persons = {p.personalnummer: p for p in db_session.query(Person).all()}
    assert persons["P001"].aktiv is True
    assert persons["P002"].aktiv is False


def test_apply_import_reuses_org_unit_across_persons(db_session):
    csv_content = make_csv(
        "P001;Anna;Admin;;IT;Technik;;;1",
        "P002;Frank;FK;;IT;Technik;;;1",
    )
    apply_import(db_session, CsvOrgSource(csv_content).fetch(), triggered_by="test")

    units = db_session.query(OrgUnit).all()
    assert len(units) == 1
    assert units[0].fachbereich == "Technik"
