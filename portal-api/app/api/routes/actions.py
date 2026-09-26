"""Massnahmen der Fuehrungskraefte und 'Was hat sich getan?' fuer das Team."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.db import get_db
from app.models.action import Action, ActionStatus
from app.models.person import Person
from app.models.result import ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Dimension

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(None, max_length=4000)
    topic: str | None = Field(None, max_length=200)
    status: ActionStatus = ActionStatus.geplant
    due_date: date | None = None
    visible_to_team: bool = True
    round_id: int | None = None


def _out(a: Action) -> dict:
    return {
        "id": a.id, "title": a.title, "description": a.description, "topic": a.topic,
        "status": a.status.value, "due_date": a.due_date.isoformat() if a.due_date else None,
        "visible_to_team": a.visible_to_team, "round_id": a.round_id,
    }


def _own(db: Session, action_id: int, user: CurrentUser) -> Action:
    a = db.get(Action, action_id)
    if a is None or a.leader_person_id != user.person.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Maßnahme nicht gefunden")
    return a


@router.get("/mine")
def my_actions(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Action).where(Action.leader_person_id == user.person.id).order_by(Action.created_at.desc())).scalars()
    return [_out(a) for a in rows]


@router.get("/team")
def team_actions(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Massnahmen der eigenen Fuehrungskraft, die diese fuer das Team freigegeben hat."""
    if not user.person.manager_personalnummer:
        return {"leader": None, "actions": []}
    leader = db.execute(select(Person).where(Person.personalnummer == user.person.manager_personalnummer)).scalar_one_or_none()
    if leader is None:
        return {"leader": None, "actions": []}
    rows = db.execute(
        select(Action).where(Action.leader_person_id == leader.id, Action.visible_to_team.is_(True)).order_by(Action.created_at.desc())
    ).scalars()
    return {"leader": leader.full_name, "actions": [_out(a) for a in rows]}


@router.get("/suggestions")
def suggestions(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Vorschlaege aus dem juengsten eigenen Report: die drei schwaechsten Dimensionen.
    Nutzt nur die bereits (>= Schwelle) aggregierten Werte der Fuehrungskraft selbst."""
    target = db.execute(
        select(RoundTarget).join(Round, Round.id == RoundTarget.round_id)
        .where(RoundTarget.leader_person_id == user.person.id, Round.status.in_((RoundStatus.ausgewertet, RoundStatus.berichtet)))
        .order_by(Round.start_at.desc())
    ).scalars().first()
    if target is None:
        return []
    rows = db.execute(
        select(Dimension.name, ResultAggregate.mean)
        .join(ResultAggregate, ResultAggregate.dimension_id == Dimension.id)
        .where(ResultAggregate.round_target_id == target.id, ResultAggregate.mean.is_not(None))
        .order_by(ResultAggregate.mean)
    ).all()[:3]
    return [
        {"topic": name, "mean": round(mean, 2), "round_id": target.round_id,
         "title": f"Handlungsfeld „{name}“ gemeinsam im Team besprechen"}
        for name, mean in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_action(payload: ActionIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    a = Action(leader_person_id=user.person.id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return _out(a)


@router.put("/{action_id}")
def update_action(action_id: int, payload: ActionIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    a = _own(db, action_id, user)
    for k, v in payload.model_dump().items():
        setattr(a, k, v)
    db.commit()
    return _out(a)


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(action_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_own(db, action_id, user))
    db.commit()
