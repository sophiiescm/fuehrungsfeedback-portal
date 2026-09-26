import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(str, enum.Enum):
    admin = "admin"
    fuehrungskraft = "fuehrungskraft"
    mitarbeiter = "mitarbeiter"


class OrgUnit(Base):
    __tablename__ = "org_unit"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    fachbereich: Mapped[str] = mapped_column(String(200), index=True)

    persons: Mapped[list["Person"]] = relationship(back_populates="org_unit")


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    personalnummer: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    vorname: Mapped[str] = mapped_column(String(200))
    nachname: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_unit.id"), nullable=True)
    manager_personalnummer: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    standort: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)  # bevorzugte Fragebogen-Sprache

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    org_unit: Mapped["OrgUnit | None"] = relationship(back_populates="persons")
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        back_populates="person", foreign_keys="RoleAssignment.person_id"
    )

    @property
    def full_name(self) -> str:
        return f"{self.vorname} {self.nachname}"


class RoleAssignment(Base):
    __tablename__ = "role_assignment"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"))
    assigned_by_person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped["Person"] = relationship(foreign_keys=[person_id], back_populates="role_assignments")
