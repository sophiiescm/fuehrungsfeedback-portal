from pydantic import BaseModel

from app.models.survey import QuestionType, SurveyVersionStatus


class DimensionOut(BaseModel):
    id: int
    name: str
    sort_order: int
    translations: dict | None = None


class DimensionIn(BaseModel):
    name: str


class QuestionOut(BaseModel):
    id: int
    dimension_id: int | None
    type: QuestionType
    text: str
    scale_min: int | None
    scale_max: int | None
    pole_label_min: str | None
    pole_label_max: str | None
    scale_labels: list[str] | None = None
    mandatory: bool
    sort_order: int
    help_text: str | None = None
    options: list[str] | None = None
    allow_multiple: bool = False
    show_if_question_id: int | None = None
    show_if_operator: str | None = None
    show_if_value: str | None = None
    translations: dict | None = None


class QuestionIn(BaseModel):
    type: QuestionType
    text: str
    dimension_id: int | None = None
    scale_min: int | None = 1
    scale_max: int | None = 5
    pole_label_min: str | None = None
    pole_label_max: str | None = None
    scale_labels: list[str] | None = None
    mandatory: bool = True
    help_text: str | None = None
    options: list[str] | None = None
    allow_multiple: bool = False
    show_if_question_id: int | None = None
    show_if_operator: str | None = None
    show_if_value: str | None = None


class QuestionUpdateIn(BaseModel):
    text: str | None = None
    dimension_id: int | None = None
    scale_min: int | None = None
    scale_max: int | None = None
    pole_label_min: str | None = None
    pole_label_max: str | None = None
    scale_labels: list[str] | None = None
    mandatory: bool | None = None
    help_text: str | None = None
    options: list[str] | None = None
    allow_multiple: bool | None = None
    show_if_question_id: int | None = None
    show_if_operator: str | None = None
    show_if_value: str | None = None


class ReorderItem(BaseModel):
    id: int
    dimension_id: int | None
    sort_order: int


class ReorderIn(BaseModel):
    questions: list[ReorderItem]


class SurveyVersionSummaryOut(BaseModel):
    id: int
    version_number: int
    status: SurveyVersionStatus
    limesurvey_template_sid: int | None


class SurveyTemplateOut(BaseModel):
    id: int
    name: str
    versions: list[SurveyVersionSummaryOut]


class SurveyTemplateCreateIn(BaseModel):
    name: str


class SurveyVersionDetailOut(BaseModel):
    id: int
    survey_template_id: int
    survey_template_name: str
    version_number: int
    status: SurveyVersionStatus
    limesurvey_template_sid: int | None
    languages: list[str] = []
    dimensions: list[DimensionOut]
    questions: list[QuestionOut]


class TransferResultOut(BaseModel):
    limesurvey_template_sid: int
