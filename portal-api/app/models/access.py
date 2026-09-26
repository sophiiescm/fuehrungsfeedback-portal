from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccessRole(Base):
    """Frei definierbare Zugriffsrolle fuer den Verwaltungsbereich (Liste von Rechten)."""

    __tablename__ = "access_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonAccessRole(Base):
    __tablename__ = "person_access_role"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), primary_key=True)
    access_role_id: Mapped[int] = mapped_column(ForeignKey("access_role.id", ondelete="CASCADE"), primary_key=True)
