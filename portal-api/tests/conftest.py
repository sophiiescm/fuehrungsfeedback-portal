import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  registriert alle Modelle
from app.db import Base, get_db
from app.main import app
from app.models.person import OrgUnit, Person, Role, RoleAssignment


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_users(db_session):
    org_unit = OrgUnit(name="Testabteilung", fachbereich="IT")
    db_session.add(org_unit)
    db_session.flush()

    admin = Person(personalnummer="T-ADMIN", vorname="Anna", nachname="Admin", org_unit_id=org_unit.id)
    leader = Person(personalnummer="T-FK", vorname="Frank", nachname="FK", org_unit_id=org_unit.id)
    employee = Person(personalnummer="T-MA", vorname="Mia", nachname="MA", org_unit_id=org_unit.id)
    db_session.add_all([admin, leader, employee])
    db_session.flush()

    db_session.add_all(
        [
            RoleAssignment(person_id=admin.id, role=Role.admin),
            RoleAssignment(person_id=leader.id, role=Role.fuehrungskraft),
            RoleAssignment(person_id=employee.id, role=Role.mitarbeiter),
        ]
    )
    db_session.commit()
    return {"admin": admin, "leader": leader, "employee": employee}
