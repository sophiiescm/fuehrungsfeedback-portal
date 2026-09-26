import base64

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db import get_db
from app.models.person import Role
from app.models.survey import Dimension, Question, QuestionType, SurveyTemplate, SurveyVersion
from app.schemas.survey import (
    DimensionIn,
    DimensionOut,
    QuestionIn,
    QuestionOut,
    QuestionUpdateIn,
    ReorderIn,
    SurveyTemplateCreateIn,
    SurveyTemplateOut,
    SurveyVersionDetailOut,
    SurveyVersionSummaryOut,
    TransferResultOut,
)
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError
from app.services.survey_export import build_tsv
from app.services.survey_publish import PublishError, publish_version
from app.services.survey_versioning import (
    VersionLockedError,
    clone_as_new_version,
    ensure_editable,
    sync_lock_status,
)

router = APIRouter(prefix="/surveys", tags=["surveys"], dependencies=[Depends(require_role(Role.admin))])


def _get_version_or_404(db: Session, version_id: int) -> SurveyVersion:
    version = db.get(SurveyVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Umfrageversion nicht gefunden")
    return version


QUESTION_FIELDS = ("id", "dimension_id", "type", "text", "scale_min", "scale_max", "pole_label_min",
                   "pole_label_max", "mandatory", "sort_order", "help_text", "options", "allow_multiple",
                   "show_if_question_id", "show_if_operator", "show_if_value")


def _q_out(q: Question) -> QuestionOut:
    return QuestionOut(**{f: getattr(q, f) for f in QUESTION_FIELDS})


def _validate_question(db: Session, version: SurveyVersion, q_type, options, show_if_question_id, show_if_operator, own_id=None):
    if q_type == QuestionType.choice and (not options or len([o for o in options if o.strip()]) < 2):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Auswahlfragen brauchen mindestens 2 Antwortoptionen")
    if show_if_question_id is not None:
        source = db.get(Question, show_if_question_id)
        if source is None or source.survey_version_id != version.id or source.id == own_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ungültige Bezugsfrage für die Verzweigung")
        if source.type == QuestionType.freitext or (source.type == QuestionType.choice and source.allow_multiple):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verzweigungen sind nur auf Skalen-, NPS- und Einfachauswahl-Fragen möglich")
        if show_if_operator not in {"eq", "neq", "lt", "lte", "gt", "gte"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ungültiger Vergleichsoperator")


def _version_to_detail(version: SurveyVersion) -> SurveyVersionDetailOut:
    return SurveyVersionDetailOut(
        id=version.id,
        survey_template_id=version.survey_template_id,
        survey_template_name=version.survey_template.name,
        version_number=version.version_number,
        status=version.status,
        limesurvey_template_sid=version.limesurvey_template_sid,
        dimensions=[
            DimensionOut(id=d.id, name=d.name, sort_order=d.sort_order)
            for d in sorted(version.dimensions, key=lambda d: d.sort_order)
        ],
        questions=[
            _q_out(q)
            for q in sorted(version.questions, key=lambda q: q.sort_order)
        ],
    )


@router.post("/templates", response_model=SurveyTemplateOut)
def create_template(payload: SurveyTemplateCreateIn, db: Session = Depends(get_db)) -> SurveyTemplateOut:
    template = SurveyTemplate(name=payload.name)
    db.add(template)
    db.flush()
    version = SurveyVersion(survey_template_id=template.id, version_number=1)
    db.add(version)
    db.commit()
    db.refresh(template)
    return SurveyTemplateOut(
        id=template.id,
        name=template.name,
        versions=[
            SurveyVersionSummaryOut(
                id=v.id, version_number=v.version_number, status=v.status,
                limesurvey_template_sid=v.limesurvey_template_sid,
            )
            for v in template.versions
        ],
    )


@router.get("/templates", response_model=list[SurveyTemplateOut])
def list_templates(db: Session = Depends(get_db)) -> list[SurveyTemplateOut]:
    templates = db.execute(select(SurveyTemplate)).scalars().all()
    result = []
    for t in templates:
        for v in t.versions:
            sync_lock_status(db, v)
        result.append(
            SurveyTemplateOut(
                id=t.id,
                name=t.name,
                versions=[
                    SurveyVersionSummaryOut(
                        id=v.id, version_number=v.version_number, status=v.status,
                        limesurvey_template_sid=v.limesurvey_template_sid,
                    )
                    for v in sorted(t.versions, key=lambda v: v.version_number)
                ],
            )
        )
    return result


@router.get("/versions/{version_id}", response_model=SurveyVersionDetailOut)
def get_version(version_id: int, db: Session = Depends(get_db)) -> SurveyVersionDetailOut:
    version = _get_version_or_404(db, version_id)
    sync_lock_status(db, version)
    return _version_to_detail(version)


@router.post("/versions/{version_id}/dimensions", response_model=DimensionOut)
def add_dimension(version_id: int, payload: DimensionIn, db: Session = Depends(get_db)) -> DimensionOut:
    version = _get_version_or_404(db, version_id)
    try:
        ensure_editable(db, version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    max_order = max([d.sort_order for d in version.dimensions], default=0)
    dim = Dimension(survey_version_id=version.id, name=payload.name, sort_order=max_order + 1)
    db.add(dim)
    db.commit()
    db.refresh(dim)
    return DimensionOut(id=dim.id, name=dim.name, sort_order=dim.sort_order)


@router.delete("/dimensions/{dimension_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dimension(dimension_id: int, db: Session = Depends(get_db)) -> None:
    dim = db.get(Dimension, dimension_id)
    if dim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dimension nicht gefunden")
    try:
        ensure_editable(db, dim.survey_version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    for q in dim.questions:
        q.dimension_id = None
    db.delete(dim)
    db.commit()


@router.post("/versions/{version_id}/questions", response_model=QuestionOut)
def add_question(version_id: int, payload: QuestionIn, db: Session = Depends(get_db)) -> QuestionOut:
    version = _get_version_or_404(db, version_id)
    try:
        ensure_editable(db, version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    _validate_question(db, version, payload.type, payload.options, payload.show_if_question_id, payload.show_if_operator)
    max_order = max([q.sort_order for q in version.questions], default=0)
    question = Question(
        survey_version_id=version.id,
        dimension_id=payload.dimension_id,
        type=payload.type,
        text=payload.text,
        scale_min=payload.scale_min,
        scale_max=payload.scale_max,
        pole_label_min=payload.pole_label_min,
        pole_label_max=payload.pole_label_max,
        mandatory=payload.mandatory,
        sort_order=max_order + 1,
        help_text=payload.help_text,
        options=[o.strip() for o in payload.options if o.strip()] if payload.options else None,
        allow_multiple=payload.allow_multiple,
        show_if_question_id=payload.show_if_question_id,
        show_if_operator=payload.show_if_operator,
        show_if_value=payload.show_if_value,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _q_out(question)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdateIn, db: Session = Depends(get_db)) -> QuestionOut:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden")
    try:
        ensure_editable(db, question.survey_version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    data = payload.model_dump(exclude_unset=True)
    _validate_question(
        db, question.survey_version, question.type, data.get("options", question.options),
        data.get("show_if_question_id", question.show_if_question_id),
        data.get("show_if_operator", question.show_if_operator), own_id=question.id,
    )
    for field, value in data.items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return _q_out(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, db: Session = Depends(get_db)) -> None:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden")
    try:
        ensure_editable(db, question.survey_version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.delete(question)
    db.commit()


@router.put("/versions/{version_id}/reorder", response_model=SurveyVersionDetailOut)
def reorder_questions(version_id: int, payload: ReorderIn, db: Session = Depends(get_db)) -> SurveyVersionDetailOut:
    version = _get_version_or_404(db, version_id)
    try:
        ensure_editable(db, version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    questions_by_id = {q.id: q for q in version.questions}
    for item in payload.questions:
        question = questions_by_id.get(item.id)
        if question is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Frage {item.id} gehoert nicht zu dieser Version")
        question.dimension_id = item.dimension_id
        question.sort_order = item.sort_order
    db.commit()
    db.refresh(version)
    return _version_to_detail(version)


@router.post("/versions/{version_id}/clone", response_model=SurveyVersionDetailOut)
def clone_version(version_id: int, db: Session = Depends(get_db)) -> SurveyVersionDetailOut:
    version = _get_version_or_404(db, version_id)
    new_version = clone_as_new_version(db, version)
    return _version_to_detail(new_version)


@router.post("/versions/{version_id}/transfer", response_model=TransferResultOut)
def transfer_to_limesurvey(version_id: int, db: Session = Depends(get_db)) -> TransferResultOut:
    version = _get_version_or_404(db, version_id)
    try:
        new_sid = publish_version(db, version)
    except PublishError as exc:
        code = status.HTTP_400_BAD_REQUEST if "keine Fragen" in str(exc) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(exc)) from exc
    return TransferResultOut(limesurvey_template_sid=new_sid)
