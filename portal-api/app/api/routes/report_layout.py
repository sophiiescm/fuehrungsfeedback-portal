"""Admin-Oberflaeche zur Gestaltung der Reports (PDF/PowerPoint/Excel/CSV)."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.routes.reports import export_response, render_export
from app.db import get_db
from app.services import report_layout, report_render

router = APIRouter(prefix="/report-layout", tags=["report-layout"], dependencies=[Depends(require_permission("surveys.manage"))])


class LayoutIn(BaseModel):
    config: dict


@router.get("")
def get_config(db: Session = Depends(get_db)) -> dict:
    return {"config": report_layout.get_layout(db), "catalog": report_layout.catalog(), "default": report_layout.DEFAULT}


@router.put("")
def put_config(payload: LayoutIn, db: Session = Depends(get_db)) -> dict:
    return {"config": report_layout.set_layout(db, payload.config)}


@router.post("/reset")
def reset(db: Session = Depends(get_db)) -> dict:
    return {"config": report_layout.set_layout(db, report_layout.DEFAULT)}


@router.post("/preview")
def preview(payload: LayoutIn) -> dict:
    """HTML-Vorschau mit Beispieldaten (ungespeicherte Konfiguration); es werden nie echte Reports verwendet."""
    return {"html": report_render.render_html(report_render.SAMPLE, payload.config)}


@router.post("/sample")
def sample(payload: LayoutIn, format: str = "pdf") -> Response:
    """Beispiel-Export in einem Format, um das Ergebnis vor dem Speichern zu pruefen."""
    if format not in ("pdf", "pptx", "xlsx", "csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekanntes Format")
    return export_response(render_export(report_render.SAMPLE, payload.config, format), format, "beispiel-report")
