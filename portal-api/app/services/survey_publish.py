"""Fragebogen-Version nach LimeSurvey veroeffentlichen (Vorlage-Umfrage anlegen/ersetzen)."""

from __future__ import annotations

import base64

from sqlalchemy.orm import Session

from app.models.survey import SurveyVersion
from app.services.limesurvey_client import LimeSurveyClient, LimeSurveyError
from app.services.survey_export import build_tsv


class PublishError(RuntimeError):
    pass


def publish_version(db: Session, version: SurveyVersion) -> int:
    if not version.questions:
        raise PublishError("Umfrageversion hat noch keine Fragen")
    data_b64 = base64.b64encode(build_tsv(version).encode("utf-8")).decode("ascii")
    client = LimeSurveyClient()
    try:
        if version.limesurvey_template_sid:
            try:
                client.delete_survey(version.limesurvey_template_sid)
            except LimeSurveyError:
                pass  # bereits geloescht oder nie erfolgreich angelegt -- einfach neu anlegen
        title = f"{version.survey_template.name} v{version.version_number}"
        sid = client.import_survey(data_b64, import_type="txt", survey_name=title)
    except LimeSurveyError as exc:
        raise PublishError(f"Übertragung nach LimeSurvey fehlgeschlagen: {exc}") from exc
    finally:
        client.close()
    version.limesurvey_template_sid = sid
    db.commit()
    return sid
