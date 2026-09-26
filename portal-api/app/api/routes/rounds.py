from fastapi import Response
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db import get_db
from app.models.person import Role
from app.models.round import Participation, ParticipationStatus, Round, RoundStatus, RoundTarget
from app.models.survey import SurveyVersion
from app.schemas.round import RoundCreateIn, RoundDashboardOut, RoundOut, RoundTargetOut
from app.services import pdf_letters
from app.services.round_lifecycle import RoundLifecycleError, close_round, start_round

router = APIRouter(prefix="/rounds", tags=["rounds"], dependencies=[Depends(require_role(Role.admin))])


def _round_to_out(r: Round) -> RoundOut:
    return RoundOut(
        id=r.id, name=r.name, survey_version_id=r.survey_version_id, status=r.status,
        start_at=r.start_at, end_at=r.end_at, reminder_days_before_end=r.reminder_days_before_end,
        report_channel=r.report_channel, target_fachbereiche=r.target_fachbereiche,
    )


@router.post("", response_model=RoundOut)
def create_round(payload: RoundCreateIn, db: Session = Depends(get_db)) -> RoundOut:
    version = db.get(SurveyVersion, payload.survey_version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Umfrageversion nicht gefunden")
    round_ = Round(
        name=payload.name,
        survey_version_id=payload.survey_version_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        reminder_days_before_end=payload.reminder_days_before_end,
        report_channel=payload.report_channel,
        target_fachbereiche=payload.target_fachbereiche,
        status=RoundStatus.geplant,
    )
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return _round_to_out(round_)


@router.get("", response_model=list[RoundOut])
def list_rounds(db: Session = Depends(get_db)) -> list[RoundOut]:
    rounds = db.execute(select(Round).order_by(Round.start_at.desc())).scalars().all()
    return [_round_to_out(r) for r in rounds]


@router.get("/{round_id}", response_model=RoundOut)
def get_round(round_id: int, db: Session = Depends(get_db)) -> RoundOut:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")
    return _round_to_out(round_)


@router.post("/{round_id}/start", response_model=RoundOut)
def start_round_endpoint(round_id: int, db: Session = Depends(get_db)) -> RoundOut:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")
    try:
        start_round(db, round_)
    except RoundLifecycleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.refresh(round_)
    return _round_to_out(round_)


@router.post("/{round_id}/close", response_model=RoundOut)
def close_round_endpoint(round_id: int, db: Session = Depends(get_db)) -> RoundOut:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")
    try:
        close_round(db, round_)
    except RoundLifecycleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.refresh(round_)
    return _round_to_out(round_)


@router.get("/{round_id}/dashboard", response_model=RoundDashboardOut)
def get_round_dashboard(round_id: int, db: Session = Depends(get_db)) -> RoundDashboardOut:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")

    targets = db.execute(select(RoundTarget).where(RoundTarget.round_id == round_id)).scalars().all()

    target_rows: list[RoundTargetOut] = []
    total_invited = 0
    total_completed = 0
    by_fachbereich: dict[str, dict[str, int | float]] = {}

    for target in targets:
        participations = db.execute(
            select(Participation).where(Participation.round_target_id == target.id)
        ).scalars().all()
        completed = sum(1 for p in participations if p.status == ParticipationStatus.erledigt)
        open_ = len(participations) - completed
        total_invited += len(participations)
        total_completed += completed

        fachbereich = target.leader.org_unit.fachbereich if target.leader.org_unit else "Unbekannt"
        bucket = by_fachbereich.setdefault(fachbereich, {"invited": 0, "completed": 0})
        bucket["invited"] += len(participations)
        bucket["completed"] += completed

        target_rows.append(
            RoundTargetOut(
                id=target.id,
                leader_person_id=target.leader_person_id,
                leader_name=target.leader.full_name,
                leader_code=target.leader_code,
                team_size_snapshot=target.team_size_snapshot,
                evaluable=target.evaluable,
                completed_count=completed,
                open_count=open_,
            )
        )

    for bucket in by_fachbereich.values():
        bucket["response_rate"] = round(bucket["completed"] / bucket["invited"], 3) if bucket["invited"] else 0.0

    return RoundDashboardOut(
        round_id=round_.id,
        status=round_.status,
        total_invited=total_invited,
        total_completed=total_completed,
        response_rate=round(total_completed / total_invited, 3) if total_invited else 0.0,
        by_fachbereich=by_fachbereich,
        targets=target_rows,
    )


def _pdf_response(html: str, name: str) -> Response:
    try:
        pdf = pdf_letters.html_to_pdf(html)
    except OSError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"PDF-Erzeugung nicht verfügbar: {exc}") from exc
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={name}"})


@router.get("/{round_id}/code-letters.pdf")
def code_letters(round_id: int, db: Session = Depends(get_db)) -> Response:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")
    return _pdf_response(pdf_letters.build_letters_html(db, round_), f"code-briefe-{round_id}.pdf")


@router.get("/{round_id}/team-notices.pdf")
def team_notices(round_id: int, db: Session = Depends(get_db)) -> Response:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Runde nicht gefunden")
    return _pdf_response(pdf_letters.build_notices_html(db, round_), f"aushang-{round_id}.pdf")
