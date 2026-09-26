from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LoginCode(Base):
    """Einmalcode fuer Personen ohne E-Mail (CLAUDE.md 'Produktionsmitarbeitende
    ohne E-Mail'). Nur der Hash wird gespeichert, nie der Klartext-Code."""

    __tablename__ = "login_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("round.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
