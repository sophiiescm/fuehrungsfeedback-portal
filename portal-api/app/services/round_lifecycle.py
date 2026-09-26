"""Lebenszyklus einer Befragungsrunde (CLAUDE.md 'Befragungsrunde
(Lebenszyklus)'): entwurf -> geplant -> offen -> geschlossen -> ausgewertet -> berichtet.

Diese Datei deckt bis 'geschlossen' ab; Auswertung/Bericht folgen in Phase 5.
"""

from __future__ import annotations

import logging
import random
import string
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.notification import Notification
from app.models.person import Person
from app.models.round import Participation, ParticipationStatus, Round, RoundStatus, RoundTarget
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError
from app.services.login_codes import create_login_code
from app.services.notifications import notify_from_template

logger = logging.getLogger(__name__)


class RoundLifecycleError(RuntimeError):
    pass


def _generate_leader_code() -> str:
    """Zufaelliges Pseudonym pro Runde, nicht aus der Personalnummer ableitbar
    (CLAUDE.md 'ein zufaelliges Pseudonym pro Runde')."""
    return "FK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def start_round(db: Session, round_: Round) -> dict:
    if round_.status not in (RoundStatus.entwurf, RoundStatus.geplant):
        raise RoundLifecycleError("Runde kann nur aus 'entwurf' oder 'geplant' gestartet werden")

    template_sid = round_.survey_version.limesurvey_template_sid
    if not template_sid:
        raise RoundLifecycleError(
            "Die Umfrageversion dieser Runde wurde noch nicht nach LimeSurvey übertragen"
        )

    settings = get_settings()

    # Org-Snapshot: aktueller Stand von `person` zum Startzeitpunkt (CLAUDE.md "Snapshot!").
    # Spaetere Org-Aenderungen wirken sich nicht rueckwirkend auf diese Runde aus, weil
    # round_target/participation eigene Zeilen sind, unabhaengig vom weiterlaufenden `person`.
    persons = db.execute(select(Person).where(Person.aktiv.is_(True))).scalars().all()
    by_pnr = {p.personalnummer: p for p in persons}
    reports_by_manager: dict[str, list[Person]] = {}
    for p in persons:
        if p.manager_personalnummer and p.manager_personalnummer in by_pnr:
            reports_by_manager.setdefault(p.manager_personalnummer, []).append(p)

    target_fachbereiche = set(round_.target_fachbereiche) if round_.target_fachbereiche else None

    stats = {"targets": 0, "evaluable_targets": 0, "participations": 0}
    client = LimeSurveyClient()
    try:
        for leader in persons:
            reports = reports_by_manager.get(leader.personalnummer, [])
            if not reports:
                continue
            if target_fachbereiche is not None:
                fachbereich = leader.org_unit.fachbereich if leader.org_unit else None
                if fachbereich not in target_fachbereiche:
                    continue

            evaluable = len(reports) >= settings.min_team_size_for_invitation
            target = RoundTarget(
                round_id=round_.id,
                leader_person_id=leader.id,
                leader_code=_generate_leader_code(),
                team_size_snapshot=len(reports),
                evaluable=evaluable,
            )
            db.add(target)
            db.flush()
            stats["targets"] += 1

            if not evaluable:
                # CLAUDE.md Anonymitaet Nr. 1: ausgeschlossen, nur "nicht auswertbar" markiert
                continue
            stats["evaluable_targets"] += 1

            try:
                new_sid = client.copy_survey(template_sid, f"{round_.name} - {target.leader_code}")
                client.activate_tokens(new_sid)
                participants_payload = [
                    {"email": r.email or "", "firstname": r.vorname, "lastname": r.nachname}
                    for r in reports
                ]
                added = client.add_participants(new_sid, participants_payload)
                client.activate_survey(new_sid)
            except LimeSurveyError:
                logger.exception("LimeSurvey-Einrichtung fuer round_target %s fehlgeschlagen", target.id)
                continue

            target.limesurvey_sid = new_sid

            for rater, added_row in zip(reports, added, strict=False):
                participation = Participation(
                    round_id=round_.id,
                    round_target_id=target.id,
                    person_id=rater.id,
                    status=ParticipationStatus.offen,
                    limesurvey_token=added_row.get("token"),
                )
                db.add(participation)
                stats["participations"] += 1
    finally:
        client.close()

    round_.status = RoundStatus.offen
    db.commit()

    _send_invitations(db, round_)
    return stats


def _feedback_link_context(round_: Round, participation: Participation) -> dict:
    settings = get_settings()
    link = None
    if participation.limesurvey_token and participation.round_target.limesurvey_sid:
        link = (
            f"{settings.limesurvey_url_public}/index.php/survey/index/"
            f"sid/{participation.round_target.limesurvey_sid}/token/{participation.limesurvey_token}"
        )
    return {
        "round_name": round_.name,
        "end_date": round_.end_at.date().isoformat(),
        "feedback_link": link,
    }


def _send_invitations(db: Session, round_: Round) -> None:
    participations = db.execute(
        select(Participation).where(Participation.round_id == round_.id)
    ).scalars().all()
    for participation in participations:
        person = db.get(Person, participation.person_id)
        context = _feedback_link_context(round_, participation)
        if person.email:
            notify_from_template(db, person, "invitation", context, round_id=round_.id)
        else:
            create_login_code(db, person, round_.id)
            notify_from_template(db, person, "invitation", context, round_id=round_.id)


def reconcile_open_participations(db: Session, round_: Round) -> int:
    """Polling-Fallback (TASKS.md Phase 4), falls der FeedbackBridge-Webhook
    ausbleibt: fragt `list_participants` je round_target ab und gleicht den
    Teilnahmestatus ab."""
    updated = 0
    open_participations = db.execute(
        select(Participation).where(
            Participation.round_id == round_.id, Participation.status == ParticipationStatus.offen
        )
    ).scalars().all()
    if not open_participations:
        return 0

    by_target: dict[int, list[Participation]] = {}
    for p in open_participations:
        by_target.setdefault(p.round_target_id, []).append(p)

    client = LimeSurveyClient()
    try:
        for target_id, participations in by_target.items():
            target = db.get(RoundTarget, target_id)
            if target is None or not target.limesurvey_sid:
                continue
            try:
                remote = client.list_participants(target.limesurvey_sid)
            except LimeSurveyError:
                logger.exception("Polling-Abgleich fuer round_target %s fehlgeschlagen", target_id)
                continue
            completed_tokens = {
                r.get("token") for r in remote if str(r.get("completed", "N")) not in ("N", "", "0")
            }
            for participation in participations:
                if participation.limesurvey_token in completed_tokens:
                    participation.status = ParticipationStatus.erledigt
                    participation.completed_date = date.today()
                    updated += 1
    finally:
        client.close()

    if updated:
        db.commit()
    return updated


def send_due_reminders(db: Session, round_: Round) -> int:
    """Erinnerungen nur an Personen, die noch nicht teilgenommen haben
    (CLAUDE.md), an den konfigurierten Tagen vor Rundenende."""
    today = date.today()
    days_before_end = (round_.end_at.date() - today).days
    if days_before_end not in round_.reminder_days_before_end:
        return 0

    open_participations = db.execute(
        select(Participation).where(
            Participation.round_id == round_.id, Participation.status == ParticipationStatus.offen
        )
    ).scalars().all()

    sent = 0
    for participation in open_participations:
        person = db.get(Person, participation.person_id)
        exists = db.execute(
            select(Notification.id).where(
                Notification.person_id == person.id,
                Notification.round_id == round_.id,
                Notification.type == "reminder",
                Notification.title.like(f"%{days_before_end}%"),
            )
        ).scalar_one_or_none()
        if exists:
            continue
        context = _feedback_link_context(round_, participation)
        context["days_left"] = days_before_end
        sent_ok = notify_from_template(db, person, "reminder", context, round_id=round_.id)
        if sent_ok:
            sent += 1
    return sent


def close_round(db: Session, round_: Round) -> None:
    if round_.status != RoundStatus.offen:
        raise RoundLifecycleError("Nur eine offene Runde kann geschlossen werden")
    reconcile_open_participations(db, round_)
    round_.status = RoundStatus.geschlossen
    db.commit()


def run_lifecycle_tick(db: Session) -> dict:
    """Vom Scheduler periodisch aufgerufen: startet faellige Runden, gleicht
    offene Teilnahmen ab, verschickt faellige Erinnerungen, schliesst
    abgelaufene Runden."""
    now = datetime.now(timezone.utc)
    result = {"started": 0, "reconciled": 0, "reminders_sent": 0, "closed": 0}

    due_to_start = db.execute(
        select(Round).where(Round.status == RoundStatus.geplant, Round.start_at <= now)
    ).scalars().all()
    for round_ in due_to_start:
        try:
            start_round(db, round_)
            result["started"] += 1
        except RoundLifecycleError:
            logger.exception("Automatischer Start von Runde %s fehlgeschlagen", round_.id)

    open_rounds = db.execute(select(Round).where(Round.status == RoundStatus.offen)).scalars().all()
    for round_ in open_rounds:
        result["reconciled"] += reconcile_open_participations(db, round_)
        result["reminders_sent"] += send_due_reminders(db, round_)
        if round_.end_at <= now:
            close_round(db, round_)
            result["closed"] += 1

    return result
