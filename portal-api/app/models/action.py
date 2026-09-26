import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActionStatus(str, enum.Enum):
    geplant = "geplant"
    in_arbeit = "in_arbeit"
    erledigt = "erledigt"


class Action(Base):
    """Massnahme einer Fuehrungskraft, abgeleitet aus dem eigenen Report ('Was hat sich getan?').

    Enthaelt nur Text der Fuehrungskraft, nie Antworten oder Freitexte; das Team sieht sie,
    wenn `visible_to_team` gesetzt ist.
    """

    __tablename__ = "action"

    id: Mapped[int] = mapped_column(primary_key=True)
    leader_person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("round.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)  # z. B. Dimension
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus, name="action_status_enum"), default=ActionStatus.geplant)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    visible_to_team: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
