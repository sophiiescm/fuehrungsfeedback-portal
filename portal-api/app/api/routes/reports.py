from fastapi import APIRouter, Depends, HTTPException, Response, status
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_role
from app.db import get_db
from app.models.person import Person, Role
from app.models.result import Report, ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Dimension, Question
from app.services import evaluation, pdf_letters
from app.services.stats import effective_threshold

router = APIRouter(tags=["reports"])
admin_router = APIRouter(dependencies=[Depends(require_role(Role.admin))], tags=["evaluation"])

VISIBLE = (RoundStatus.ausgewertet, RoundStatus.berichtet)

REPORT_HTML = """<html><head><meta charset="utf-8"><style>
body{font-family:'DejaVu Sans',sans-serif;font-size:10pt}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ccc;padding:4px;text-align:left}.bar{background:#4f46e5;height:10px}</style></head><body>
<h1>Feedback-Report: {{ d.round_name }}</h1><p>{{ d.leader_name }} · {{ d.n_responses }} Antworten</p>
<h2>Dimensionen</h2><table><tr><th>Dimension</th><th>Mittelwert</th><th>Median</th><th>Std.abw.</th><th>Min/Max</th><th>Fachbereich</th><th>Unternehmen</th><th>Vorrunde</th></tr>
{% for x in d.dimensions %}<tr><td>{{ x.dimension }}</td><td>{{ x.mean }}<div class="bar" style="width:{{ x.mean * 20 }}%"></div></td><td>{{ x.median }}</td><td>{{ x.stddev }}</td><td>{{ x.min }}/{{ x.max }}</td>
<td>{{ x.fachbereich.mean if x.fachbereich else '–' }}</td><td>{{ x.unternehmen.mean if x.unternehmen else '–' }}</td><td>{{ x.vorrunde.mean if x.vorrunde else '–' }}</td></tr>{% endfor %}</table>
<h2>Fragen</h2><table>{% for q in d.questions %}<tr><td>{{ q.question }}</td><td>{{ q.mean }}</td><td>n={{ q.n }}</td><td>{{ q.distribution }}</td></tr>{% endfor %}</table>
{% if d.ai_summary %}<h2>Zusammenfassung der Freitexte</h2><p>{{ d.ai_summary }}</p>{% endif %}
{% if d.freetext %}<h2>Freitexte (geschwärzt)</h2><ul>{% for t in d.freetext %}<li>{{ t }}</li>{% endfor %}</ul>{% endif %}
</body></html>"""


def _agg_dict(a: ResultAggregate) -> dict:
    return {
        "n": a.n, "min": a.min_value, "max": a.max_value, "mean": a.mean,
        "median": a.median, "stddev": a.stddev, "distribution": a.distribution,
    }


def group_mean(db: Session, round_id: int, dimension_id: int, fachbereich: str | None = None) -> dict | None:
    """Mittelwert der Fuehrungskraft-Mittelwerte; None bei < Schwelle Fuehrungskraeften
    (Unterdrueckung kleiner Gruppen auch bei Vergleichswerten)."""
    rows = db.execute(
        select(ResultAggregate.mean, RoundTarget.leader_person_id)
        .join(RoundTarget, RoundTarget.id == ResultAggregate.round_target_id)
        .where(RoundTarget.round_id == round_id, ResultAggregate.dimension_id == dimension_id)
    ).all()
    if fachbereich is not None:
        allowed = {
            p.id for p in db.execute(select(Person)).scalars()
            if p.org_unit and p.org_unit.fachbereich == fachbereich
        }
        rows = [r for r in rows if r[1] in allowed]
    if len(rows) < effective_threshold():
        return None
    return {"mean": round(sum(r[0] for r in rows) / len(rows), 3), "leaders": len(rows)}


def _report_detail(db: Session, target: RoundTarget) -> dict:
    report = db.execute(select(Report).where(Report.round_target_id == target.id)).scalar_one_or_none()
    base = {
        "target_id": target.id, "round_id": target.round_id,
        "round_name": target.round.name, "leader_name": target.leader.full_name,
    }
    if report is None or report.suppressed:
        return {
            **base, "available": False, "n_responses": report.n_responses if report else 0,
            "message": f"Für diese Runde liegen weniger als {effective_threshold()} abgeschlossene Antworten vor. "
                       "Zum Schutz der Anonymität wird kein Report angezeigt.",
        }

    fach = target.leader.org_unit.fachbereich if target.leader.org_unit else None
    prev = db.execute(
        select(RoundTarget).join(Round, Round.id == RoundTarget.round_id)
        .where(
            RoundTarget.leader_person_id == target.leader_person_id,
            RoundTarget.round_id != target.round_id,
            Round.start_at < target.round.start_at,
        )
        .order_by(Round.start_at.desc())
    ).scalars().first()

    aggs = db.execute(select(ResultAggregate).where(ResultAggregate.round_target_id == target.id)).scalars().all()
    dims = []
    dim_rows = db.execute(
        select(Dimension).where(Dimension.survey_version_id == target.round.survey_version_id).order_by(Dimension.sort_order)
    ).scalars()
    for d in dim_rows:
        own = next((a for a in aggs if a.dimension_id == d.id), None)
        if own is None:
            continue
        prev_agg = None
        if prev:
            prev_agg = db.execute(
                select(ResultAggregate).where(
                    ResultAggregate.round_target_id == prev.id, ResultAggregate.dimension_id == d.id
                )
            ).scalar_one_or_none()
        dims.append({
            "dimension": d.name, **_agg_dict(own),
            "fachbereich": group_mean(db, target.round_id, d.id, fach),
            "unternehmen": group_mean(db, target.round_id, d.id),
            "vorrunde": {"mean": prev_agg.mean, "delta": round(own.mean - prev_agg.mean, 3)} if prev_agg else None,
        })
    questions = []
    q_rows = db.execute(
        select(Question).where(Question.survey_version_id == target.round.survey_version_id).order_by(Question.sort_order)
    ).scalars()
    for q in q_rows:
        a = next((x for x in aggs if x.question_id == q.id), None)
        if a:
            questions.append({"question": q.text, **_agg_dict(a)})
    return {
        **base, "available": True, "n_responses": report.n_responses, "dimensions": dims,
        "questions": questions, "freetext": report.freetext or [], "ai_summary": report.ai_summary,
    }


def _own_target(db: Session, target_id: int, user: CurrentUser) -> RoundTarget:
    target = db.get(RoundTarget, target_id)
    # Rechtepruefung: ausschliesslich die bewertete Fuehrungskraft selbst (auch Admins nicht)
    if target is None or target.leader_person_id != user.person.id or target.round.status not in VISIBLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report nicht gefunden")
    return target


@router.get("/reports/mine")
def my_reports(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    targets = db.execute(
        select(RoundTarget).join(Round, Round.id == RoundTarget.round_id)
        .where(
            RoundTarget.leader_person_id == user.person.id,
            RoundTarget.evaluable.is_(True),
            Round.status.in_(VISIBLE),
        )
        .order_by(Round.start_at.desc())
    ).scalars().all()
    return [{"target_id": t.id, "round_name": t.round.name, "start": t.round.start_at.date().isoformat()} for t in targets]


@router.get("/reports/mine/trend")
def my_trend(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    targets = db.execute(
        select(RoundTarget).join(Round, Round.id == RoundTarget.round_id)
        .where(RoundTarget.leader_person_id == user.person.id, Round.status.in_(VISIBLE))
        .order_by(Round.start_at)
    ).scalars().all()
    series: dict[str, list[dict]] = {}
    for t in targets:
        rows = db.execute(
            select(ResultAggregate).where(
                ResultAggregate.round_target_id == t.id, ResultAggregate.dimension_id.is_not(None)
            )
        ).scalars()
        for a in rows:
            name = db.get(Dimension, a.dimension_id).name
            series.setdefault(name, []).append({"round": t.round.name, "mean": a.mean})
    return {"series": series}


@router.get("/reports/{target_id}")
def report_detail(target_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return _report_detail(db, _own_target(db, target_id, user))


@router.get("/reports/{target_id}/pdf")
def report_pdf(target_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    detail = _report_detail(db, _own_target(db, target_id, user))
    if not detail["available"]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail["message"])
    try:
        pdf = pdf_letters.html_to_pdf(Template(REPORT_HTML).render(d=detail))
    except OSError as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"PDF nicht verfügbar: {exc}") from exc
    return Response(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{target_id}.pdf"},
    )


@admin_router.post("/rounds/{round_id}/evaluate")
def evaluate(round_id: int, db: Session = Depends(get_db)) -> dict:
    round_ = db.get(Round, round_id)
    if round_ is None:
        raise HTTPException(404, "Runde nicht gefunden")
    try:
        return evaluation.evaluate_round(db, round_)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@admin_router.post("/rounds/{round_id}/distribute")
def distribute(round_id: int, db: Session = Depends(get_db)) -> dict:
    round_ = db.get(Round, round_id)
    if round_ is None or round_.status != RoundStatus.ausgewertet:
        raise HTTPException(409, "Runde muss ausgewertet sein")
    return {"sent": evaluation.distribute_reports(db, round_)}


@admin_router.get("/benchmark")
def benchmark(round_id: int, fachbereich: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Pseudonymisiertes Benchmarking (FK-A, FK-B, ...). Gruppen mit weniger als
    der Schwelle an Fuehrungskraeften werden komplett unterdrueckt."""
    rows = db.execute(
        select(RoundTarget).where(RoundTarget.round_id == round_id, RoundTarget.evaluable.is_(True))
    ).scalars().all()
    groups: dict[str, list[dict]] = {}
    for t in rows:
        fach = t.leader.org_unit.fachbereich if t.leader.org_unit else "Unbekannt"
        if fachbereich and fach != fachbereich:
            continue
        aggs = db.execute(
            select(ResultAggregate).where(
                ResultAggregate.round_target_id == t.id, ResultAggregate.dimension_id.is_not(None)
            )
        ).scalars().all()
        if aggs:
            groups.setdefault(fach, []).append({db.get(Dimension, a.dimension_id).name: a.mean for a in aggs})

    out: dict = {}
    for fach, members in groups.items():
        if len(members) < effective_threshold():
            out[fach] = {"suppressed": True, "leaders": len(members)}
            continue
        ranked = sorted(members, key=lambda m: -sum(m.values()))  # Reihenfolge nach Ergebnis, Namen nie
        out[fach] = {
            "suppressed": False,
            "leaders": [{"pseudonym": f"FK-{chr(65 + i % 26) * (1 + i // 26)}", "dimensions": m} for i, m in enumerate(ranked)],
        }
    if not fachbereich:
        all_members = [m for ms in groups.values() for m in ms]
        if len(all_members) < effective_threshold():
            out["_gesamt"] = {"suppressed": True}
        else:
            keys = {k for m in all_members for k in m}
            out["_gesamt"] = {
                "suppressed": False, "leaders": len(all_members),
                "mean_by_dimension": {
                    k: round(sum(m[k] for m in all_members if k in m) / sum(1 for m in all_members if k in m), 3)
                    for k in keys
                },
            }
    return out
