"""Auswertung einer geschlossenen Runde (CLAUDE.md 'Auswertung').

Pro auswertbarer Fuehrungskraft: Antworten aus LimeSurvey exportieren
(die Survey-ID IST die Zuordnung, siehe ENTSCHEIDUNGEN Nr. 9), Statistik
pro Frage und Dimension, Berichtsschwelle >= 3 durchsetzen, Freitexte
schwaerzen + mischen, optional KI-Zusammenfassung. Es werden nur Aggregate
und geschwaerzte Freitexte gespeichert, nie Einzelantworten mit Personenbezug.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.notification import Notification  # noqa: F401
from app.models.person import Person
from app.models.result import Report, ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Question, QuestionType
from app.services import ai
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError
from app.services.notifications import notify_from_template
from app.services.redaction import build_name_pattern, redact_and_shuffle
from app.services.stats import compute_stats, effective_threshold

logger = logging.getLogger(__name__)


def _to_number(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _evaluate_choice(db: Session, target: RoundTarget, q: Question, responses: list[dict]) -> None:
    """Auswahlfragen: Haeufigkeit je Option (Einfach- wie Mehrfachauswahl); n = antwortende Personen."""
    options = q.options or []
    counts = {o: 0 for o in options}
    answered = 0
    for r in responses:
        if q.allow_multiple:
            picked = [options[i] for i in range(len(options)) if r.get(f"Q{q.id}[SQ{i + 1:03d}]") == "Y"]
        else:
            code = _to_number(r.get(f"Q{q.id}"))
            picked = [options[int(code) - 1]] if code and 1 <= int(code) <= len(options) else []
        if picked:
            answered += 1
            for o in picked:
                counts[o] += 1
    if answered >= effective_threshold():
        db.add(ResultAggregate(round_target_id=target.id, question_id=q.id, n=answered, distribution=counts))


def evaluate_target(db: Session, target: RoundTarget, responses: list[dict], name_pattern, pnrs: set[str]) -> Report:
    """Reine Berechnung auf bereits exportierten Antworten (testbar ohne LimeSurvey)."""
    db.execute(delete(ResultAggregate).where(ResultAggregate.round_target_id == target.id))
    report = db.execute(select(Report).where(Report.round_target_id == target.id)).scalar_one_or_none()
    if report is None:
        report = Report(round_target_id=target.id)
        db.add(report)

    report.n_responses = len(responses)
    report.generated_at = datetime.now(timezone.utc)
    if len(responses) < effective_threshold():
        report.suppressed = True
        report.freetext = None
        report.ai_summary = None
        db.commit()
        return report
    report.suppressed = False

    questions = db.execute(
        select(Question).where(Question.survey_version_id == target.round.survey_version_id)
    ).scalars().all()

    per_dimension: dict[int, list[list[float]]] = {}  # dimension_id -> Liste je Antwort
    freetext_groups: list[dict] = []
    all_texts: list[str] = []
    threshold = effective_threshold()
    for q in questions:
        col = f"Q{q.id}"
        if q.type == QuestionType.freitext:
            texts = redact_and_shuffle([r[col] for r in responses if isinstance(r.get(col), str)], name_pattern, pnrs)
            if len(texts) >= threshold:  # zu wenige Texte je Frage -> Rueckschluss moeglich, nicht anzeigen
                freetext_groups.append({"question_id": q.id, "question": q.text, "texts": texts})
                all_texts += texts
            continue
        if q.type == QuestionType.choice:
            _evaluate_choice(db, target, q, responses)
            continue
        values = [n for r in responses if (n := _to_number(r.get(col))) is not None]
        st = compute_stats(values)
        if st:
            db.add(ResultAggregate(round_target_id=target.id, question_id=q.id, n=st.n, min_value=st.min,
                                   max_value=st.max, mean=st.mean, median=st.median, stddev=st.stddev,
                                   distribution=st.distribution))
        if q.dimension_id and q.type == QuestionType.likert:
            per_dimension.setdefault(q.dimension_id, [])
            for i, r in enumerate(responses):
                n = _to_number(r.get(col))
                if n is None:
                    continue
                while len(per_dimension[q.dimension_id]) <= i:
                    per_dimension[q.dimension_id].append([])
                per_dimension[q.dimension_id][i].append(n)

    for dim_id, rows in per_dimension.items():
        means = [sum(v) / len(v) for v in rows if v]  # ein Wert je antwortender Person
        st = compute_stats(means)
        if st:
            db.add(ResultAggregate(round_target_id=target.id, dimension_id=dim_id, n=st.n, min_value=st.min,
                                   max_value=st.max, mean=st.mean, median=st.median, stddev=st.stddev,
                                   distribution=st.distribution))

    report.freetext = freetext_groups or None
    report.ai_summary = ai.summarize(all_texts) if all_texts else None
    db.commit()
    return report


def _org_redaction_inputs(db: Session):
    persons = db.execute(select(Person)).scalars().all()
    names = {p.vorname for p in persons} | {p.nachname for p in persons} | {f"{p.vorname} {p.nachname}" for p in persons}
    return build_name_pattern(names), {p.personalnummer for p in persons}


def evaluate_round(db: Session, round_: Round) -> dict:
    if round_.status != RoundStatus.geschlossen:
        raise ValueError("Nur geschlossene Runden koennen ausgewertet werden")
    name_pattern, pnrs = _org_redaction_inputs(db)
    stats = {"evaluated": 0, "suppressed": 0, "failed": 0}
    client = LimeSurveyClient()
    try:
        for target in db.execute(select(RoundTarget).where(RoundTarget.round_id == round_.id, RoundTarget.evaluable.is_(True))).scalars():
            if not target.limesurvey_sid:
                continue
            try:
                raw = client.export_responses(target.limesurvey_sid)
                responses = json.loads(raw.decode("utf-8"))["responses"] if raw else []
            except (LimeSurveyError, ValueError, KeyError):
                logger.exception("Export fuer round_target %s fehlgeschlagen", target.id)
                stats["failed"] += 1
                continue
            report = evaluate_target(db, target, responses, name_pattern, pnrs)
            stats["suppressed" if report.suppressed else "evaluated"] += 1
    finally:
        client.close()
    round_.status = RoundStatus.ausgewertet
    db.commit()
    return stats


def distribute_reports(db: Session, round_: Round) -> int:
    """Report an die Fuehrungskraefte verfuegbar machen und benachrichtigen
    (Kanal portal/email/beides: die In-Portal-Benachrichtigung existiert immer)."""
    sent = 0
    for target in db.execute(select(RoundTarget).where(RoundTarget.round_id == round_.id, RoundTarget.evaluable.is_(True))).scalars():
        report = db.execute(select(Report).where(Report.round_target_id == target.id)).scalar_one_or_none()
        if report is None or report.suppressed or report.sent_at:
            continue
        ctx = {"round_name": round_.name}
        if notify_from_template(db, target.leader, "report_ready", ctx, round_id=round_.id):
            report.sent_at = datetime.now(timezone.utc)
            sent += 1
    round_.status = RoundStatus.berichtet
    db.commit()
    return sent
