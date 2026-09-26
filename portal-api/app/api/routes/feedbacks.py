import hashlib
import hmac
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.core.config import get_settings
from app.db import get_db
from app.models.round import Participation, ParticipationStatus, Round, RoundTarget
from app.schemas.feedback_webhook import LimeSurveyCompleteWebhookIn
from app.schemas.round import MyFeedbackOut

router = APIRouter(tags=["feedbacks"])


@router.get("/feedbacks/mine", response_model=list[MyFeedbackOut])
def my_feedbacks(
    current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MyFeedbackOut]:
    settings = get_settings()
    participations = db.execute(
        select(Participation).where(Participation.person_id == current_user.person.id)
    ).scalars().all()

    result = []
    for p in participations:
        round_ = db.get(Round, p.round_id)
        target = db.get(RoundTarget, p.round_target_id)
        link = None
        if p.status == ParticipationStatus.offen and p.limesurvey_token and target.limesurvey_sid:
            link = (
                f"{settings.limesurvey_url_public}/index.php/survey/index/"
                f"sid/{target.limesurvey_sid}/token/{p.limesurvey_token}"
            )
        result.append(
            MyFeedbackOut(
                participation_id=p.id,
                round_name=round_.name,
                leader_name=target.leader.full_name,
                status=p.status,
                due_date=round_.end_at.date().isoformat(),
                feedback_link=link,
                completed_date=p.completed_date.isoformat() if p.completed_date else None,
            )
        )
    return result


@router.post("/feedbacks/webhook/limesurvey-complete")
def limesurvey_complete_webhook(
    payload: LimeSurveyCompleteWebhookIn, db: Session = Depends(get_db)
) -> dict:
    """Wird vom LimeSurvey-Plugin FeedbackBridge bei afterSurveyComplete
    aufgerufen (HMAC-signiert, siehe limesurvey-plugin/FeedbackBridge).
    Setzt NUR den Teilnahmestatus, liest nie Antwortinhalte (CLAUDE.md)."""
    settings = get_settings()
    expected = hmac.new(
        settings.feedbackbridge_hmac_secret.encode("utf-8"),
        f"{payload.sid}:{payload.token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, payload.signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültige Signatur")

    target = db.execute(
        select(RoundTarget).where(RoundTarget.limesurvey_sid == payload.sid)
    ).scalar_one_or_none()
    if target is None:
        return {"status": "ignored"}

    participation = db.execute(
        select(Participation).where(
            Participation.round_target_id == target.id, Participation.limesurvey_token == payload.token
        )
    ).scalar_one_or_none()
    if participation is None:
        return {"status": "ignored"}

    participation.status = ParticipationStatus.erledigt
    participation.completed_date = date.today()
    db.commit()
    return {"status": "ok"}
