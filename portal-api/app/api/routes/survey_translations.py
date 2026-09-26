"""Uebersetzungen des Fragebogens (Editor) und Sprachwahl der Nutzer."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.core.config import get_settings
from app.db import get_db
from app.models.person import Person
from app.models.survey import Dimension, Question, QuestionType, SurveyVersion
from app.services import ai
from app.services.languages import DEFAULT_LANGUAGE, LANGUAGES, TRANSLATABLE_QUESTION_FIELDS, catalog
from app.services.survey_versioning import VersionLockedError, ensure_editable

router = APIRouter(prefix="/surveys", tags=["survey-translations"], dependencies=[Depends(require_permission("surveys.manage"))])
public_router = APIRouter(tags=["languages"])


class LanguagesIn(BaseModel):
    languages: list[str]


class QuestionTranslationIn(BaseModel):
    text: str | None = None
    help_text: str | None = None
    options: list[str] | None = None
    scale_labels: list[str] | None = None
    pole_label_min: str | None = None
    pole_label_max: str | None = None


class DimensionTranslationIn(BaseModel):
    name: str


def _lang(code: str) -> str:
    if code == DEFAULT_LANGUAGE or code not in LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte oder Standardsprache")
    return code


def _editable(db: Session, version: SurveyVersion) -> None:
    try:
        ensure_editable(db, version)
    except VersionLockedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.put("/versions/{version_id}/languages")
def set_languages(version_id: int, payload: LanguagesIn, db: Session = Depends(get_db)) -> dict:
    version = db.get(SurveyVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Umfrageversion nicht gefunden")
    _editable(db, version)
    langs = []
    for c in payload.languages:
        if c not in langs and c != DEFAULT_LANGUAGE:
            langs.append(_lang(c))
    version.languages = langs
    db.commit()
    return {"languages": langs}


@router.put("/questions/{question_id}/translations/{lang}")
def set_question_translation(question_id: int, lang: str, payload: QuestionTranslationIn, db: Session = Depends(get_db)) -> dict:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden")
    _editable(db, q.survey_version)
    _lang(lang)
    data = payload.model_dump(exclude_unset=True)
    if "options" in data and data["options"] is not None and len(data["options"]) != len(q.options or []):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Anzahl der Optionen muss zur deutschen Fassung passen")
    if "scale_labels" in data and data["scale_labels"] is not None and len(data["scale_labels"]) != len(q.scale_labels or []):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Anzahl der Skalenbeschriftungen muss zur deutschen Fassung passen")
    current = dict((q.translations or {}).get(lang) or {})
    current.update({k: v for k, v in data.items() if k in TRANSLATABLE_QUESTION_FIELDS})
    q.translations = {**(q.translations or {}), lang: current}
    db.commit()
    return {"translations": q.translations}


@router.put("/dimensions/{dimension_id}/translations/{lang}")
def set_dimension_translation(dimension_id: int, lang: str, payload: DimensionTranslationIn, db: Session = Depends(get_db)) -> dict:
    d = db.get(Dimension, dimension_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dimension nicht gefunden")
    _editable(db, d.survey_version)
    _lang(lang)
    d.translations = {**(d.translations or {}), lang: {"name": payload.name.strip()}}
    db.commit()
    return {"translations": d.translations}


@router.post("/versions/{version_id}/translate")
def auto_translate(version_id: int, lang: str, db: Session = Depends(get_db)) -> dict:
    """Fehlende Uebersetzungen per KI-Provider vorschlagen (falls eingerichtet). Bereits gepflegte Felder bleiben unberuehrt;
    Ergebnisse sind Vorschlaege und sollten fachlich geprueft werden."""
    version = db.get(SurveyVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Umfrageversion nicht gefunden")
    _editable(db, version)
    _lang(lang)
    if get_settings().ai_provider == "none":
        raise HTTPException(status.HTTP_409_CONFLICT, "Kein KI-Provider eingerichtet (AI_PROVIDER) – bitte manuell übersetzen")

    todo: list[dict] = []
    for q in version.questions:
        have = (q.translations or {}).get(lang) or {}
        item: dict = {"id": f"q{q.id}"}
        if q.text and not have.get("text"):
            item["text"] = q.text
        if q.help_text and not have.get("help_text"):
            item["help_text"] = q.help_text
        if q.options and not have.get("options"):
            item["options"] = q.options
        if q.scale_labels and not have.get("scale_labels"):
            item["scale_labels"] = q.scale_labels
        if len(item) > 1:
            todo.append(item)
    for d in version.dimensions:
        if not ((d.translations or {}).get(lang) or {}).get("name"):
            todo.append({"id": f"d{d.id}", "name": d.name})
    if not todo:
        return {"translated": 0}

    prompt = (
        f"Übersetze die folgenden Texte eines Mitarbeiterbefragungs-Fragebogens (Feedback an Führungskräfte) vom Deutschen ins {LANGUAGES[lang]} "
        f"(Sprachcode {lang}). Behalte Aufbau und Listenlängen exakt bei, verwende einfache, respektvolle Sprache. "
        "Antworte ausschließlich mit einem JSON-Array derselben Objekte (gleiche Schlüssel, inkl. id), ohne weiteren Text.\n\n"
        + json.dumps(todo, ensure_ascii=False)
    )
    raw = ai._chat(prompt, max_tokens=8000)
    try:
        result = json.loads(raw[raw.index("["): raw.rindex("]") + 1]) if raw else []
    except ValueError:
        result = []
    by_id = {r.get("id"): r for r in result if isinstance(r, dict)}
    count = 0
    for q in version.questions:
        r = by_id.get(f"q{q.id}")
        if not r:
            continue
        cur = dict((q.translations or {}).get(lang) or {})
        for k in ("text", "help_text"):
            if isinstance(r.get(k), str) and r[k].strip() and not cur.get(k):
                cur[k] = r[k].strip()
        for k, base in (("options", q.options), ("scale_labels", q.scale_labels)):
            v = r.get(k)
            if isinstance(v, list) and base and len(v) == len(base) and all(isinstance(x, str) and x.strip() for x in v) and not cur.get(k):
                cur[k] = [x.strip() for x in v]
        if cur:
            q.translations = {**(q.translations or {}), lang: cur}
            count += 1
    for d in version.dimensions:
        r = by_id.get(f"d{d.id}")
        if r and isinstance(r.get("name"), str) and r["name"].strip():
            d.translations = {**(d.translations or {}), lang: {"name": r["name"].strip()}}
            count += 1
    db.commit()
    if count == 0:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Die Übersetzung durch den KI-Provider hat kein verwertbares Ergebnis geliefert")
    return {"translated": count}


# ------------------------------------------------------------------ Nutzer: Sprachwahl
def used_languages(db: Session) -> list[str]:
    codes = {DEFAULT_LANGUAGE}
    for langs in db.execute(select(SurveyVersion.languages)).scalars():
        codes.update(c for c in (langs or []) if c in LANGUAGES)
    return [c for c in LANGUAGES if c in codes]


class UserLanguageIn(BaseModel):
    language: str


@public_router.get("/languages")
def list_languages(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Katalog und die Sprachen, in denen es mindestens einen Fragebogen gibt; dazu die eigene Einstellung."""
    used = used_languages(db)
    return {
        "catalog": catalog(), "available": [c for c in catalog() if c["code"] in used],
        "mine": user.person.language or DEFAULT_LANGUAGE,
    }


@public_router.put("/auth/me/language")
def set_my_language(payload: UserLanguageIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.language not in LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Sprache")
    person = db.get(Person, user.person.id)
    person.language = payload.language
    db.commit()
    return {"language": payload.language}
