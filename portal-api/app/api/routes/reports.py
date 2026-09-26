from fastapi import APIRouter, Depends, HTTPException, Response, status
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.db import get_db
from app.models.person import Person, Role
from app.models.result import Report, ResultAggregate
from app.models.round import Round, RoundStatus, RoundTarget
from app.models.survey import Dimension, Question, QuestionType
from app.models.system import Setting
from app.services import evaluation, pdf_letters, report_layout, report_render, textanalysis
from app.services import report_render_bench
from app.services.stats import effective_threshold

router = APIRouter(tags=["reports"])
admin_router = APIRouter(dependencies=[Depends(require_permission("rounds.manage", view_perms=("results.view",)))], tags=["evaluation"])

VISIBLE = (RoundStatus.ausgewertet, RoundStatus.berichtet)

def nps_from_distribution(dist: dict) -> dict:
    """NPS = Anteil Promoter (9-10) minus Anteil Detractors (0-6), in Prozentpunkten."""
    counts = {int(k): v for k, v in dist.items()}
    n = sum(counts.values())
    prom = sum(v for k, v in counts.items() if k >= 9)
    det = sum(v for k, v in counts.items() if k <= 6)
    return {
        "score": round((prom - det) / n * 100, 1) if n else None, "n": n,
        "promoters": prom, "passives": n - prom - det, "detractors": det,
    }


def get_nps_reference(db: Session) -> dict | None:
    s = db.execute(select(Setting).where(Setting.key == "nps_reference")).scalar_one_or_none()
    return s.value if s else None


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


def _assignment(groups: list[dict], all_texts: list[str]) -> dict[str, str]:
    """Gespeicherte Kategorien (bei der Auswertung erzeugt), sonst Schluesselwort-Fallback."""
    out: dict[str, str] = {}
    for g in groups:
        for t, c in zip(g["texts"], g.get("cats") or []):
            out[t] = c
    return out if out else textanalysis.categorize_keywords(all_texts)


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
    nps = None
    q_rows = db.execute(
        select(Question).where(Question.survey_version_id == target.round.survey_version_id).order_by(Question.sort_order)
    ).scalars()
    for q in q_rows:
        a = next((x for x in aggs if x.question_id == q.id), None)
        if a:
            item = {"question": q.text, "type": q.type.value, "options": q.options, **_agg_dict(a)}
            if q.type == QuestionType.nps:
                nps = nps_from_distribution(a.distribution)
                item["nps"] = nps
            questions.append(item)
    groups = report.freetext or []
    if groups and isinstance(groups[0], str):  # aeltere Reports (Phase 5): flache Liste
        groups = [{"question_id": None, "question": "Freitext", "texts": groups}]
    all_texts = [t for g in groups for t in g["texts"]]
    return {
        **base, "available": True, "n_responses": report.n_responses, "dimensions": dims,
        "questions": questions, "nps": nps, "nps_reference": get_nps_reference(db),
        "freetext": groups, "wordcloud": textanalysis.wordcloud(all_texts),
        "categories": textanalysis.group_by_category(all_texts, _assignment(groups, all_texts)),
        "ai_summary": report.ai_summary,
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


EXPORT_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}


def render_export(detail: dict, layout: dict, fmt: str) -> bytes:
    if fmt == "pdf":
        try:
            return pdf_letters.html_to_pdf(report_render.render_html(detail, layout))
        except OSError as exc:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"PDF nicht verfügbar: {exc}") from exc
    if fmt == "pptx":
        return report_render.build_pptx(detail, layout)
    if fmt == "xlsx":
        return report_render.build_xlsx(detail, layout)
    if fmt == "csv":
        return report_render.build_csv(detail, layout).encode("utf-8")
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekanntes Format (pdf, pptx, xlsx, csv)")


def export_response(data: bytes, fmt: str, name: str) -> Response:
    return Response(data, media_type=EXPORT_TYPES[fmt], headers={"Content-Disposition": f"attachment; filename={name}.{fmt}"})


@router.get("/reports/{target_id}/export")
def report_export(target_id: int, format: str = "pdf", user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Eigener Report als PDF, PowerPoint, Excel oder CSV -- gestaltet nach dem Admin-Layout."""
    detail = _report_detail(db, _own_target(db, target_id, user))
    if not detail["available"]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail["message"])
    return export_response(render_export(detail, report_layout.get_layout(db), format), format, f"report-{target_id}")


@router.get("/reports/{target_id}/pdf")
def report_pdf(target_id: int, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    return report_export(target_id, "pdf", user, db)


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


@admin_router.get("/benchmark/export.csv")
def benchmark_export(round_id: int, db: Session = Depends(get_db)) -> Response:
    """Mittelwerte je Fachbereich und Dimension (nur Gruppen >= Schwelle, keine Personen)."""
    data = benchmark(round_id, None, db)
    dims = sorted({k for g in data.values() if not g.get("suppressed") and isinstance(g.get("leaders"), list) for m in g["leaders"] for k in m["dimensions"]})
    lines = ["fachbereich;fuehrungskraefte;" + ";".join(dims)]
    for fb, g in sorted(data.items()):
        if fb == "_gesamt" or g.get("suppressed") or not isinstance(g.get("leaders"), list):
            continue
        ms = [m["dimensions"] for m in g["leaders"]]
        cells = []
        for d in dims:
            vals = [m[d] for m in ms if d in m]
            cells.append(f"{sum(vals) / len(vals):.2f}".replace(".", ",") if vals else "")
        lines.append(f"{fb};{len(ms)};" + ";".join(cells))
    return Response("\ufeff" + "\n".join(lines) + "\n", media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=benchmark-{round_id}.csv"})


def _bench_round(db: Session, round_id: int) -> str:
    r = db.get(Round, round_id)
    if r is None:
        raise HTTPException(404, "Runde nicht gefunden")
    return r.name


@admin_router.get("/benchmark/export.xlsx")
def benchmark_xlsx(round_id: int, db: Session = Depends(get_db)) -> Response:
    _bench_round(db, round_id)
    dims, rows = report_render_bench.benchmark_table(benchmark(round_id, None, db))
    return export_response(report_render_bench.benchmark_xlsx(dims, rows, report_layout.get_layout(db)["accent"]), "xlsx", f"benchmark-{round_id}")


@admin_router.get("/benchmark/export.pptx")
def benchmark_pptx(round_id: int, db: Session = Depends(get_db)) -> Response:
    name = _bench_round(db, round_id)
    dims, rows = report_render_bench.benchmark_table(benchmark(round_id, None, db))
    return export_response(report_render_bench.benchmark_pptx(name, dims, rows, report_layout.get_layout(db)["accent"]), "pptx", f"benchmark-{round_id}")


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


TRAFFIC_LIGHT_DELTA = 0.2  # Abweichung zum Unternehmensmittel in Skalenpunkten


def traffic_light(delta: float | None) -> str | None:
    if delta is None:
        return None
    return "gruen" if delta >= TRAFFIC_LIGHT_DELTA else "rot" if delta <= -TRAFFIC_LIGHT_DELTA else "gelb"


def _group_nps(db: Session, round_id: int, fachbereich: str | None) -> dict | None:
    nps_q = db.execute(
        select(Question).join(Round, Round.survey_version_id == Question.survey_version_id)
        .where(Round.id == round_id, Question.type == QuestionType.nps)
    ).scalars().first()
    if nps_q is None:
        return None
    rows = db.execute(
        select(ResultAggregate.distribution, RoundTarget.leader_person_id)
        .join(RoundTarget, RoundTarget.id == ResultAggregate.round_target_id)
        .where(RoundTarget.round_id == round_id, ResultAggregate.question_id == nps_q.id)
    ).all()
    if fachbereich is not None:
        allowed = {
            p.id for p in db.execute(select(Person)).scalars()
            if p.org_unit and p.org_unit.fachbereich == fachbereich
        }
        rows = [r for r in rows if r[1] in allowed]
    if len(rows) < effective_threshold():
        return None
    total: dict[str, int] = {}
    for dist, _ in rows:
        for k, v in dist.items():
            total[k] = total.get(k, 0) + v
    return {**nps_from_distribution(total), "leaders": len(rows)}


@admin_router.get("/benchmark/compare")
def benchmark_compare(round_id: int, groups: str, db: Session = Depends(get_db)) -> dict:
    """Vergleich frei waehlbarer Gruppen (Fachbereiche, kommagetrennt), z. B. "Vertrieb,IT".
    Je Gruppe und Dimension: Mittelwert, Abweichung zum Unternehmen, Ampel. Gruppen mit
    weniger als der Schwelle an Fuehrungskraeften werden unterdrueckt."""
    names = [g.strip() for g in groups.split(",") if g.strip()]
    dims = db.execute(
        select(Dimension).join(Round, Round.survey_version_id == Dimension.survey_version_id)
        .where(Round.id == round_id).order_by(Dimension.sort_order)
    ).scalars().all()
    result: dict = {"dimensions": [d.name for d in dims], "groups": {}, "company": {}}
    for d in dims:
        c = group_mean(db, round_id, d.id)
        result["company"][d.name] = c["mean"] if c else None
    for name in names:
        row: dict = {}
        n_leaders = 0
        for d in dims:
            g = group_mean(db, round_id, d.id, name)
            if g is None:
                row[d.name] = None
                continue
            n_leaders = g["leaders"]
            comp = result["company"][d.name]
            delta = round(g["mean"] - comp, 3) if comp is not None else None
            row[d.name] = {"mean": g["mean"], "delta": delta, "ampel": traffic_light(delta)}
        result["groups"][name] = {
            "suppressed": all(v is None for v in row.values()), "leaders": n_leaders,
            "dimensions": row, "nps": _group_nps(db, round_id, name),
        }
    result["company_nps"] = _group_nps(db, round_id, None)
    result["nps_reference"] = get_nps_reference(db)
    return result


@admin_router.get("/nps/reference")
def get_reference(db: Session = Depends(get_db)) -> dict:
    return get_nps_reference(db) or {"value": None, "label": ""}


@admin_router.put("/nps/reference")
def put_reference(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Manuell hinterlegter Vergleichs-NPS (z. B. Branchenwert) fuer das externe Benchmarking."""
    value = {"value": float(payload["value"]), "label": str(payload.get("label", ""))[:200]}
    s = db.execute(select(Setting).where(Setting.key == "nps_reference")).scalar_one_or_none()
    if s is None:
        db.add(Setting(key="nps_reference", value=value))
    else:
        s.value = value
    db.commit()
    return value
