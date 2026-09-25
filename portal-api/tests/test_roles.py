from sqlalchemy import select

from app.models.person import OrgUnit, Person, Role, RoleAssignment
from app.services.roles import recompute_roles


def _make_person(db_session, org_unit, pnr, manager=None, aktiv=True):
    person = Person(
        personalnummer=pnr, vorname=pnr, nachname=pnr, org_unit_id=org_unit.id,
        manager_personalnummer=manager, aktiv=aktiv,
    )
    db_session.add(person)
    db_session.flush()
    return person


def test_recompute_roles_grants_mitarbeiter_to_all_active(db_session):
    org_unit = OrgUnit(name="IT", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()
    p1 = _make_person(db_session, org_unit, "P001")
    db_session.commit()

    recompute_roles(db_session)

    roles = db_session.execute(select(RoleAssignment).where(RoleAssignment.person_id == p1.id)).scalars().all()
    assert [r.role for r in roles] == [Role.mitarbeiter]


def test_recompute_roles_grants_fuehrungskraft_with_active_report(db_session):
    org_unit = OrgUnit(name="IT", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()
    leader = _make_person(db_session, org_unit, "P001")
    _make_person(db_session, org_unit, "P002", manager="P001")
    db_session.commit()

    recompute_roles(db_session)

    roles = {
        r.role
        for r in db_session.execute(select(RoleAssignment).where(RoleAssignment.person_id == leader.id)).scalars()
    }
    assert roles == {Role.mitarbeiter, Role.fuehrungskraft}


def test_recompute_roles_revokes_fuehrungskraft_when_team_shrinks_to_zero(db_session):
    org_unit = OrgUnit(name="IT", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()
    leader = _make_person(db_session, org_unit, "P001")
    report = _make_person(db_session, org_unit, "P002", manager="P001")
    db_session.commit()
    recompute_roles(db_session)

    # Team schrumpft auf 0 (letzter Mitarbeiter verlaesst das Unternehmen)
    report.aktiv = False
    db_session.commit()
    recompute_roles(db_session)

    roles = {
        r.role
        for r in db_session.execute(select(RoleAssignment).where(RoleAssignment.person_id == leader.id)).scalars()
    }
    assert roles == {Role.mitarbeiter}


def test_recompute_roles_never_touches_admin(db_session):
    org_unit = OrgUnit(name="IT", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()
    admin = _make_person(db_session, org_unit, "P001")
    db_session.add(RoleAssignment(person_id=admin.id, role=Role.admin))
    db_session.commit()

    recompute_roles(db_session)

    roles = {
        r.role
        for r in db_session.execute(select(RoleAssignment).where(RoleAssignment.person_id == admin.id)).scalars()
    }
    assert Role.admin in roles
