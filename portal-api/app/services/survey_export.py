"""Wandelt eine `SurveyVersion` in das LimeSurvey-TSV-Umfrageformat um (die
".txt"-Variante von `import_survey`, siehe docs/ENTSCHEIDUNGEN.md Nr. 19).

Format-Referenz (aus der laufenden LimeSurvey-Instanz ausgelesen,
`application/helpers/admin/import_helper.php::TSVImportSurvey`): tab-getrennte
Zeilen mit einer Kopfzeile, `class`-Spalte unterscheidet Zeilentyp:
  S  = Umfrage-Einstellung (name/text = Spaltenname/Wert in `lime_surveys`)
  SL = Sprachspezifische Umfrage-Einstellung (z.B. surveyls_title)
  G  = Fragengruppe (= Dimension). name = Anzeigename, text = Beschreibung
  Q  = Frage. type/scale = LimeSurvey-Fragetyp, name = Code, text = Text
  A  = Antwortoption (Fragetyp 'L')
  SQ = Unterfrage (Fragetyp 'M' = Mehrfachauswahl)

Fragetypen: likert -> L (Skala 4-7), nps -> L mit Codes 0-10, freitext -> T,
choice -> L (Einfachauswahl, Code = Position) bzw. M (Mehrfachauswahl,
Unterfragen SQ001..). Verzweigungen werden als LimeSurvey-Relevance-Ausdruck
exportiert.
"""

from __future__ import annotations

import csv
import io

from app.core.config import get_settings
from app.services.languages import LANGUAGES, dimension_name_in, question_in
from app.models.survey import Question, QuestionType, SurveyVersion

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
    "showprogress": "Y",
    "template": "feedbackportal",  # mobil optimiertes Portal-Theme (Fallback: LimeSurvey-Standard)
}

TSV_COLUMNS = [
    "class", "type/scale", "name", "text", "relevance", "language",
    "mandatory", "help", "validation", "default",
]

_OPS = {"eq": "==", "neq": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}


def _row(class_: str, **fields: str) -> dict[str, str]:
    row = dict.fromkeys(TSV_COLUMNS, "")
    row["class"] = class_
    row.update(fields)
    return row


def question_code(q: Question) -> str:
    return f"Q{q.id}"


def choice_code(q: Question, value: str) -> str:
    """Wert der Bedingung einer Einfachauswahl (Optionstext) -> Antwortcode (Position, 1-basiert)."""
    options = q.options or []
    return str(options.index(value) + 1) if value in options else value


def relevance_for(q: Question, all_questions: dict[int, Question]) -> str:
    if not q.show_if_question_id or q.show_if_question_id not in all_questions:
        return "1"
    source = all_questions[q.show_if_question_id]
    if source.sort_order >= q.sort_order or q.show_if_operator not in _OPS or q.show_if_value is None:
        return "1"  # ungueltige/rueckwaertige Bedingung: Frage immer zeigen (nie versehentlich verstecken)
    value = choice_code(source, q.show_if_value) if source.type == QuestionType.choice else q.show_if_value
    literal = value if value.replace(".", "", 1).lstrip("-").isdigit() else f'"{value}"'
    return f"(({question_code(source)}.NAOK {_OPS[q.show_if_operator]} {literal}))"


def build_tsv(version: SurveyVersion, language: str = "de") -> str:
    """LimeSurvey-TSV. Mehrsprachig: je Sprache ein kompletter Block (gleiche Gruppen-Reihenfolge und
    gleiche Fragecodes, wie vom LimeSurvey-Importer verlangt); fehlende Uebersetzungen fallen auf Deutsch zurueck."""
    extra = [c for c in (version.languages or []) if c in LANGUAGES and c != language]
    langs = [language] + extra
    rows: list[dict[str, str]] = []

    rows.append(_row("S", name="language", text=language))
    if extra:
        rows.append(_row("S", name="additional_languages", text=" ".join(extra)))
    for key, value in MANDATORY_SURVEY_SETTINGS.items():
        rows.append(_row("S", name=key, text=value))

    title = version.survey_template.name if version.survey_template else f"Umfrage {version.id}"
    portal = get_settings().portal_public_url.rstrip("/")
    for lang in langs:
        rows.append(_row("SL", name="surveyls_title", text=f"{title} (v{version.version_number})", language=lang))
        rows.append(_row("SL", name="surveyls_url", text=f"{portal}/feedbacks/quittung", language=lang))
        rows.append(_row("SL", name="surveyls_urldescription", text=UI_TEXT["portal_link"].get(lang, UI_TEXT["portal_link"]["en"] if lang != "de" else UI_TEXT["portal_link"]["de"]), language=lang))

    ordered_dimensions = sorted(version.dimensions, key=lambda d: d.sort_order)
    by_id = {q.id: q for q in version.questions}
    questions_by_dimension: dict[int | None, list[Question]] = {}
    for q in sorted(version.questions, key=lambda q: q.sort_order):
        questions_by_dimension.setdefault(q.dimension_id, []).append(q)

    groups = [(dimension_name_in_de(dim), dim, questions_by_dimension.get(dim.id, [])) for dim in ordered_dimensions]
    ungrouped = questions_by_dimension.get(None, [])
    if ungrouped:
        groups.append(("Weitere Fragen", None, ungrouped))

    for lang in langs:
        for group_name, dim, questions in groups:
            if not questions:
                continue
            gname = dimension_name_in(dim, lang) if dim is not None else UI_TEXT["more_questions"].get(lang, UI_TEXT["more_questions"]["en"] if lang != "de" else "Weitere Fragen")
            rows.append(_row("G", name=gname, text="", language=lang))
            for q in questions:
                code = question_code(q)
                t = question_in(q, lang)
                common = dict(
                    name=code, text=t["text"], mandatory="Y" if q.mandatory else "N", language=lang,
                    relevance=relevance_for(q, by_id), help=t["help_text"],
                )
                if q.type == QuestionType.freitext:
                    rows.append(_row("Q", **{"type/scale": "T"}, **common))
                elif q.type == QuestionType.nps:
                    rows.append(_row("Q", **{"type/scale": "L"}, **common))
                    for point in range(0, 11):
                        label = ""
                        if point == 0:
                            label = t["pole_label_min"] or UI_TEXT["nps_min"].get(lang, UI_TEXT["nps_min"]["en"] if lang != "de" else UI_TEXT["nps_min"]["de"])
                        elif point == 10:
                            label = t["pole_label_max"] or UI_TEXT["nps_max"].get(lang, UI_TEXT["nps_max"]["en"] if lang != "de" else UI_TEXT["nps_max"]["de"])
                        rows.append(_row("A", **{"type/scale": "0"}, name=str(point), text=label or str(point), language=lang))
                elif q.type == QuestionType.choice and q.allow_multiple:
                    rows.append(_row("Q", **{"type/scale": "M"}, **common))
                    for i, option in enumerate(t["options"], start=1):
                        rows.append(_row("SQ", name=f"SQ{i:03d}", text=option, language=lang))
                elif q.type == QuestionType.choice:
                    rows.append(_row("Q", **{"type/scale": "L"}, **common))
                    for i, option in enumerate(t["options"], start=1):
                        rows.append(_row("A", **{"type/scale": "0"}, name=str(i), text=option, language=lang))
                else:  # likert
                    rows.append(_row("Q", **{"type/scale": "L"}, **common))
                    scale_min = q.scale_min or 1
                    scale_max = q.scale_max or 5
                    for point in range(scale_min, scale_max + 1):
                        label = ""
                        idx = point - scale_min
                        if t["scale_labels"] and len(t["scale_labels"]) == scale_max - scale_min + 1:
                            label = t["scale_labels"][idx]
                        elif point == scale_min:
                            label = t["pole_label_min"] or str(point)
                        elif point == scale_max:
                            label = t["pole_label_max"] or str(point)
                        rows.append(_row("A", **{"type/scale": "0"}, name=str(point), text=label or str(point), language=lang))  # Zwischenstufen mit Zahl beschriftet

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TSV_COLUMNS, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def dimension_name_in_de(dim) -> str:
    return dim.name


UI_TEXT = {
    "portal_link": {"de": "Weiter zum Portal", "en": "Continue to the portal", "tr": "Portala devam et", "pl": "Przejdź do portalu", "ru": "Перейти в портал",
                    "ro": "Continuă către portal", "uk": "Перейти до порталу", "ar": "المتابعة إلى البوابة", "es": "Continuar al portal", "fr": "Continuer vers le portail",
                    "it": "Continua al portale"},
    "more_questions": {"de": "Weitere Fragen", "en": "More questions", "tr": "Diğer sorular", "pl": "Dodatkowe pytania", "ru": "Дополнительные вопросы",
                       "ro": "Alte întrebări", "uk": "Додаткові запитання", "ar": "أسئلة إضافية", "es": "Más preguntas", "fr": "Autres questions", "it": "Altre domande"},
    "nps_min": {"de": "Sehr unwahrscheinlich", "en": "Not at all likely", "tr": "Hiç olası değil", "pl": "Bardzo mało prawdopodobne", "ru": "Совсем маловероятно",
                "ro": "Foarte puțin probabil", "uk": "Дуже малоймовірно", "ar": "غير محتمل إطلاقًا", "es": "Nada probable", "fr": "Pas du tout probable", "it": "Per niente probabile"},
    "nps_max": {"de": "Sehr wahrscheinlich", "en": "Extremely likely", "tr": "Kesinlikle olası", "pl": "Bardzo prawdopodobne", "ru": "Очень вероятно",
                "ro": "Foarte probabil", "uk": "Дуже ймовірно", "ar": "محتمل جدًا", "es": "Muy probable", "fr": "Très probable", "it": "Molto probabile"},
}
