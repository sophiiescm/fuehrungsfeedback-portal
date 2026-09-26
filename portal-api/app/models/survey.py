import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SurveyVersionStatus(str, enum.Enum):
    entwurf = "entwurf"
    gesperrt = "gesperrt"  # in Nutzung durch mind. eine Runde -> nicht mehr editierbar


class QuestionType(str, enum.Enum):
    likert = "likert"
    freitext = "freitext"
    choice = "choice"  # Einfach-/Mehrfachauswahl (allow_multiple)
    nps = "nps"  # Net Promoter Score, Skala 0-10


class SurveyTemplate(Base):
    __tablename__ = "survey_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions: Mapped[list["SurveyVersion"]] = relationship(back_populates="survey_template")


class SurveyVersion(Base):
    __tablename__ = "survey_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_template_id: Mapped[int] = mapped_column(ForeignKey("survey_template.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[SurveyVersionStatus] = mapped_column(
        Enum(SurveyVersionStatus, name="survey_version_status_enum"),
        default=SurveyVersionStatus.entwurf,
    )
    # LimeSurvey-Vorlagen-Survey-ID, sobald einmal per import_survey uebertragen (Phase 3)
    limesurvey_template_sid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    survey_template: Mapped["SurveyTemplate"] = relationship(back_populates="versions")
    dimensions: Mapped[list["Dimension"]] = relationship(
        back_populates="survey_version", order_by="Dimension.sort_order"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="survey_version", order_by="Question.sort_order"
    )


class Dimension(Base):
    __tablename__ = "dimension"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_version_id: Mapped[int] = mapped_column(ForeignKey("survey_version.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    survey_version: Mapped["SurveyVersion"] = relationship(back_populates="dimensions")
    questions: Mapped[list["Question"]] = relationship(back_populates="dimension")


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_version_id: Mapped[int] = mapped_column(ForeignKey("survey_version.id"), index=True)
    dimension_id: Mapped[int | None] = mapped_column(ForeignKey("dimension.id"), nullable=True)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type_enum"))
    text: Mapped[str] = mapped_column(Text)
    scale_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scale_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pole_label_min: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pole_label_max: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mandatory: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Code der Frage in LimeSurvey (z.B. "G01Q03"), gesetzt nach Uebertragung
    limesurvey_question_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # nur choice: Antwortoptionen
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False)  # nur choice
    # Verzweigung: Frage nur anzeigen, wenn die Bezugsfrage die Bedingung erfuellt
    show_if_question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="SET NULL"), nullable=True)
    show_if_operator: Mapped[str | None] = mapped_column(String(5), nullable=True)  # eq neq lt lte gt gte
    show_if_value: Mapped[str | None] = mapped_column(String(100), nullable=True)

    survey_version: Mapped["SurveyVersion"] = relationship(back_populates="questions")
    dimension: Mapped["Dimension | None"] = relationship(back_populates="questions")
    show_if_question: Mapped["Question | None"] = relationship(remote_side="Question.id", foreign_keys=[show_if_question_id])
