from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UsedAssertion(Base):
    """Bereits eingeloeste Trusted-App-SSO-Assertions (Replay-Schutz, Einmalverwendung)."""

    __tablename__ = "used_assertion"

    jti: Mapped[str] = mapped_column(String(100), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
