import base64

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db import get_db
from app.models.person import Role
from app.models.survey import Dimension, Question, SurveyTemplate, SurveyVersion
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
            QuestionOut(
                id=q.id, dimension_id=q.dimension_id, type=q.type, text=q.text,
                scale_min=q.scale_min, scale_max=q.scale_max,
                pole_label_min=q.pole_label_min, pole_label_max=q.pole_label_max,
                mandatory=q.mandatory, sort_order=q.sort_order,
            )
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
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return QuestionOut(
        id=question.id, dimension_id=question.dimension_id, type=question.type, text=question.text,
        scale_min=question.scale_min, scale_max=question.scale_max,
        pole_label_min=question.pole_label_min, pole_label_max=question.pole_label_max,
        mandatory=question.mandatory, sort_order=question.sort_order,
    )


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdateIn, db: Session = Depends(get_db)) -> QuestionOut:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden")
    try:
        ensure_editable(db, question.survey_version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return QuestionOut(
        id=question.id, dimension_id=question.dimension_id, type=question.type, text=question.text,
        scale_min=question.scale_min, scale_max=question.scale_max,
        pole_label_min=question.pole_label_min, pole_label_max=question.pole_label_max,
        mandatory=question.mandatory, sort_order=question.sort_order,
    )


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
    if not version.questions:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Umfrageversion hat noch keine Fragen")

    tsv = build_tsv(version)
    data_b64 = base64.b64encode(tsv.encode("utf-8")).decode("ascii")

    client = LimeSurveyClient()
    try:
        if version.limesurvey_template_sid:
            try:
                client.delete_survey(version.limesurvey_template_sid)
            except LimeSurveyError:
                pass  # bereits geloescht oder nie erfolgreich angelegt -- einfach neu anlegen
        title = f"{version.survey_template.name} v{version.version_number}"
        new_sid = client.import_survey(data_b64, import_type="txt", survey_name=title)
    except LimeSurveyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Übertragung nach LimeSurvey fehlgeschlagen: {exc}") from exc
    finally:
        client.close()

    version.limesurvey_template_sid = new_sid
    db.commit()
    return TransferResultOut(limesurvey_template_sid=new_sid)
