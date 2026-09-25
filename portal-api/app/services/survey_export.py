"""Wandelt eine `SurveyVersion` in das LimeSurvey-TSV-Umfrageformat um (die
".txt"-Variante von `import_survey`, siehe docs/ENTSCHEIDUNGEN.md Nr. 19).

Format-Referenz (aus der laufenden LimeSurvey-Instanz ausgelesen,
`application/helpers/admin/import_helper.php::TSVImportSurvey`): tab-getrennte
Zeilen mit einer Kopfzeile, `class`-Spalte unterscheidet Zeilentyp:
  S  = Umfrage-Einstellung (name/text = Spaltenname/Wert in `lime_surveys`)
  SL = Sprachspezifische Umfrage-Einstellung (z.B. surveyls_title)
  G  = Fragengruppe (= Dimension). name = Anzeigename, text = Beschreibung
  Q  = Frage. type/scale = LimeSurvey-Fragetyp, name = Code, text = Text
  A  = Antwortoption (nur bei Fragetyp 'L' = Liste/Radio, fuer Likert-Skalen)
"""

from __future__ import annotations

import csv
import io

from app.models.survey import QuestionType, SurveyVersion

# CLAUDE.md Anonymitaetsregeln, immer erzwungen (siehe docs/limesurvey-analyse.md):
MANDATORY_SURVEY_SETTINGS = {
    "anonymized": "Y",
    "datestamp": "N",
    "ipaddr": "N",
    "ipanonymize": "N",
    "printanswers": "Y",
    "tokenanswerspersistence": "Y",
    "alloweditaftercompletion": "N",
    "format": "G",  # Gruppe fuer Gruppe anzeigen
}

TSV_COLUMNS = [
    "class", "type/scale", "name", "text", "relevance", "language",
    "mandatory", "help", "validation", "default",
]


def _row(class_: str, **fields: str) -> dict[str, str]:
    row = dict.fromkeys(TSV_COLUMNS, "")
    row["class"] = class_
    row.update(fields)
    return row


def build_tsv(version: SurveyVersion, language: str = "de") -> str:
    rows: list[dict[str, str]] = []

    rows.append(_row("S", name="language", text=language))
    for key, value in MANDATORY_SURVEY_SETTINGS.items():
        rows.append(_row("S", name=key, text=value))

    title = version.survey_template.name if version.survey_template else f"Umfrage {version.id}"
    rows.append(_row("SL", name="surveyls_title", text=f"{title} (v{version.version_number})", language=language))

    # Dimensionen (in Reihenfolge) als Gruppen, danach eine Sammelgruppe fuer
    # Fragen ohne Dimension (Freitext).
    ordered_dimensions = sorted(version.dimensions, key=lambda d: d.sort_order)
    questions_by_dimension: dict[int | None, list] = {}
    for q in sorted(version.questions, key=lambda q: q.sort_order):
        questions_by_dimension.setdefault(q.dimension_id, []).append(q)

    groups: list[tuple[str, list]] = []
    for dim in ordered_dimensions:
        groups.append((dim.name, questions_by_dimension.get(dim.id, [])))
    ungrouped = questions_by_dimension.get(None, [])
    if ungrouped:
        groups.append(("Weitere Fragen", ungrouped))

    for group_name, questions in groups:
        if not questions:
            continue
        rows.append(_row("G", name=group_name, text=""))
        for idx, q in enumerate(questions, start=1):
            code = f"Q{q.id}" if q.id else f"Q{idx}"
            if q.type == QuestionType.freitext:
                rows.append(
                    _row(
                        "Q", **{"type/scale": "T"}, name=code, text=q.text,
                        mandatory="Y" if q.mandatory else "N", language=language, relevance="1",
                    )
                )
            else:
                rows.append(
                    _row(
                        "Q", **{"type/scale": "L"}, name=code, text=q.text,
                        mandatory="Y" if q.mandatory else "N", language=language, relevance="1",
                    )
                )
                scale_min = q.scale_min or 1
                scale_max = q.scale_max or 5
                for point in range(scale_min, scale_max + 1):
                    label = ""
                    if point == scale_min:
                        label = q.pole_label_min or str(point)
                    elif point == scale_max:
                        label = q.pole_label_max or str(point)
                    rows.append(_row("A", **{"type/scale": "0"}, name=str(point), text=label, language=language))

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TSV_COLUMNS, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()
