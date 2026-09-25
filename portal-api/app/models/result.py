from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ResultAggregate(Base):
    """Aggregierte Statistik pro Frage ODER Dimension und Fuehrungskraft/Runde.

    Es werden nur Aggregate gespeichert, nie Einzelantworten (CLAUDE.md Anonymitaet).
    Wird erst erzeugt, wenn n >= min_responses_for_report (Berichtsschwelle).
    """

    __tablename__ = "result_aggregate"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_target_id: Mapped[int] = mapped_column(ForeignKey("round_target.id"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id"), nullable=True)
    dimension_id: Mapped[int | None] = mapped_column(ForeignKey("dimension.id"), nullable=True)

    n: Mapped[int] = mapped_column(Integer)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    median: Mapped[float | None] = mapped_column(Float, nullable=True)
    stddev: Mapped[float | None] = mapped_column(Float, nullable=True)
    distribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"1": 2, "2": 5, ...}

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_target_id: Mapped[int] = mapped_column(ForeignKey("round_target.id"), index=True, unique=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
