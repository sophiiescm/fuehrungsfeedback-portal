import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RoundStatus(str, enum.Enum):
    entwurf = "entwurf"
    geplant = "geplant"
    offen = "offen"
    geschlossen = "geschlossen"
    ausgewertet = "ausgewertet"
    berichtet = "berichtet"


class ReportChannel(str, enum.Enum):
    portal = "portal"
    email = "email"
    beides = "beides"


class ParticipationStatus(str, enum.Enum):
    offen = "offen"
    erledigt = "erledigt"


class Round(Base):
    """Eine Befragungsrunde. Siehe CLAUDE.md 'Befragungsrunde (Lebenszyklus)'."""

    __tablename__ = "round"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    survey_version_id: Mapped[int] = mapped_column(ForeignKey("survey_version.id"), index=True)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, name="round_status_enum"), default=RoundStatus.entwurf
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reminder_days_before_end: Mapped[list[int]] = mapped_column(JSON, default=lambda: [7, 2])
    report_channel: Mapped[ReportChannel] = mapped_column(
        Enum(ReportChannel, name="report_channel_enum"), default=ReportChannel.portal
    )
    # None = alle Fachbereiche, sonst Liste von Fachbereich-Namen
    target_fachbereiche: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    survey_version: Mapped["SurveyVersion"] = relationship()  # noqa: F821
    targets: Mapped[list["RoundTarget"]] = relationship(back_populates="round")


class RoundTarget(Base):
    """Eine bewertete Fuehrungskraft innerhalb einer Runde = eine eigene LimeSurvey-Umfrage.

    Siehe docs/ENTSCHEIDUNGEN.md Nr. 9: die Zuordnung Antwort->Fuehrungskraft
    ergibt sich aus limesurvey_sid, nicht aus einem Feld in der Antwort.
    """

    __tablename__ = "round_target"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("round.id"), index=True)
    leader_person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    # Zufaelliges Pseudonym, u.a. fuer Benchmark-Anzeige ("FK-A", "FK-B" wird daraus abgeleitet)
    leader_code: Mapped[str] = mapped_column(String(50), unique=True)
    limesurvey_sid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_size_snapshot: Mapped[int] = mapped_column(Integer)
    evaluable: Mapped[bool] = mapped_column(Boolean, default=False)  # team_size_snapshot >= Schwelle

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    round: Mapped["Round"] = relationship(back_populates="targets")
    leader: Mapped["Person"] = relationship()  # noqa: F821
    participations: Mapped[list["Participation"]] = relationship(back_populates="round_target")


class Participation(Base):
    """Speichert NUR dass jemand teilgenommen hat, nie was (CLAUDE.md Anonymitaet Nr. 3)."""

    __tablename__ = "participation"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("round.id"), index=True)
    round_target_id: Mapped[int] = mapped_column(ForeignKey("round_target.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)  # die bewertende Person
    status: Mapped[ParticipationStatus] = mapped_column(
        Enum(ParticipationStatus, name="participation_status_enum"), default=ParticipationStatus.offen
    )
    # Nur Datum, kein Zeitstempel (CLAUDE.md: "keinen exakten Abschlusszeitpunkt speichern")
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # LimeSurvey-Token fuer den Zugriffslink dieser Person auf round_target.limesurvey_sid.
    # Verknuepft Person<->Teilnahme-Status, nie Person<->Antwortinhalt.
    limesurvey_token: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    round_target: Mapped["RoundTarget"] = relationship(back_populates="participations")
