"""Rendert einen Report (Detail-Dict aus reports._report_detail) gemaess Layout als HTML/PDF, PowerPoint,
Excel und CSV. Die Exporte enthalten nur bereits aggregierte/geschwaerzte Daten (nie Rohantworten)."""

from __future__ import annotations

import csv
import io
import re
from datetime import date

from jinja2 import Environment
from markupsafe import Markup, escape

from app.services.report_layout import PLACEHOLDERS, TEXTS, normalize

SAMPLE: dict = {
    "available": True, "round_name": "Beispiel-Runde H1/2026", "leader_name": "Alex Beispiel", "n_responses": 12,
    "dimensions": [
        {"dimension": "Kommunikation", "mean": 3.9, "median": 4.0, "stddev": 0.8, "min": 2, "max": 5, "n": 12,
         "distribution": {"1": 0, "2": 1, "3": 3, "4": 5, "5": 3}, "fachbereich": {"mean": 3.7}, "unternehmen": {"mean": 3.6}, "vorrunde": {"mean": 3.7, "delta": 0.2}},
        {"dimension": "Wertschätzung", "mean": 4.3, "median": 4.0, "stddev": 0.6, "min": 3, "max": 5, "n": 12,
         "distribution": {"1": 0, "2": 0, "3": 2, "4": 5, "5": 5}, "fachbereich": {"mean": 3.9}, "unternehmen": {"mean": 3.8}, "vorrunde": {"mean": 4.2, "delta": 0.1}},
        {"dimension": "Entwicklung", "mean": 3.2, "median": 3.0, "stddev": 1.0, "min": 1, "max": 5, "n": 12,
         "distribution": {"1": 1, "2": 2, "3": 4, "4": 3, "5": 2}, "fachbereich": {"mean": 3.5}, "unternehmen": {"mean": 3.6}, "vorrunde": {"mean": 3.4, "delta": -0.2}},
        {"dimension": "Entscheidungsfindung", "mean": 3.8, "median": 4.0, "stddev": 0.7, "min": 2, "max": 5, "n": 12,
         "distribution": {"1": 0, "2": 1, "3": 3, "4": 6, "5": 2}, "fachbereich": {"mean": 3.7}, "unternehmen": {"mean": 3.7}, "vorrunde": None},
    ],
    "questions": [
        {"question": "Meine Führungskraft kommuniziert Erwartungen klar.", "type": "likert", "options": None, "n": 12, "mean": 4.0, "median": 4.0, "stddev": 0.7, "min": 2, "max": 5, "distribution": {"2": 1, "3": 2, "4": 6, "5": 3}},
        {"question": "Welche Themen sind Ihnen wichtig?", "type": "choice", "options": ["Kommunikation", "Wertschätzung", "Weiterentwicklung"], "n": 12, "mean": None, "distribution": {"1": 6, "2": 4, "3": 8}},
    ],
    "nps": {"score": 25.0, "n": 12, "promoters": 5, "passives": 5, "detractors": 2},
    "nps_reference": {"value": 10, "label": "Branche"},
    "freetext": [{"question": "Was schätzen Sie besonders?", "texts": ["Offene und ehrliche Gespräche.", "Gute Erreichbarkeit.", "Faire Verteilung der Aufgaben."]}],
    "categories": [{"category": "Kommunikation", "count": 3, "texts": ["Offene und ehrliche Gespräche.", "Gute Erreichbarkeit.", "Klare Ansagen."]}],
    "wordcloud": [{"word": "Gespräche", "count": 5}, {"word": "Aufgaben", "count": 4}, {"word": "Team", "count": 3}],
    "ai_summary": "Das Team schätzt die offene Kommunikation und die faire Aufgabenverteilung. Gewünscht sind mehr Entwicklungsgespräche.",
}


def _f(v, d=2):
    return "–" if v is None else f"{v:.{d}f}".replace(".", ",")


def choice_label(q: dict, key) -> str:
    opts = q.get("options") or []
    try:
        i = int(key) - 1
        return opts[i] if 0 <= i < len(opts) else str(key)
    except (ValueError, TypeError):
        return str(key)


def md_html(text: str) -> Markup:
    """Einfache Formatierung: Absaetze (Leerzeile), Aufzaehlung ('- '), **fett**. Alles andere wird maskiert."""
    blocks = re.split(r"\n\s*\n", (text or "").strip())
    out = []
    for b in blocks:
        lines = [ln for ln in b.split("\n") if ln.strip()]
        if not lines:
            continue

        def inline(t: str) -> str:
            return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(t)))

        if all(ln.lstrip().startswith("- ") for ln in lines):
            out.append("<ul>" + "".join(f"<li>{inline(ln.lstrip()[2:])}</li>" for ln in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(inline(ln) for ln in lines) + "</p>")
    return Markup("".join(out))


def md_lines(text: str) -> list[str]:
    """Fuer PowerPoint: Absaetze/Aufzaehlungen als Textzeilen (ohne **)."""
    lines = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r"\*\*(.+?)\*\*", r"\1", ln)
        lines.append("• " + ln[2:] if ln.startswith("- ") else ln)
    return lines


def _fill(t: str, values: dict) -> str:
    """Platzhalter {name} ersetzen; unbekannte Platzhalter bleiben sichtbar stehen."""
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), t or "")


def darken(hex_color: str, factor: float = 0.4) -> str:
    """Dunklere Variante fuer Text/Ueberschriften (helle Markenfarbe hat auf Weiss zu wenig Kontrast)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * (1 - factor)), int(g * (1 - factor)), int(b * (1 - factor)))


def prepare(detail: dict, layout: dict) -> dict:
    layout = normalize(layout)
    dims = detail.get("dimensions") or []
    avg = lambda xs: (sum(xs) / len(xs)) if xs else None  # noqa: E731
    ordered = sorted(dims, key=lambda d: -d["mean"])
    overall = avg([d["mean"] for d in dims])
    prev = avg([d["vorrunde"]["mean"] for d in dims]) if dims and all(d.get("vorrunde") for d in dims) else None
    comp = avg([d["unternehmen"]["mean"] for d in dims]) if dims and all(d.get("unternehmen") for d in dims) else None
    best = ordered[0]["dimension"] if ordered else ""
    weak = ordered[-1]["dimension"] if ordered else ""
    nps = detail.get("nps") or {}
    fmt = dict(
        round=detail.get("round_name", ""), leader=detail.get("leader_name", ""), n=detail.get("n_responses", 0),
        date=date.today().strftime("%d.%m.%Y"), overall=_f(overall, 1) if overall is not None else "–",
        overall_delta_prev=(("+" if overall - prev >= 0 else "−") + _f(abs(overall - prev), 1)) if overall is not None and prev is not None else "–",
        company_avg=_f(comp, 1) if comp is not None else "–", best_topic=best, weak_topic=weak,
        nps=nps.get("score") if nps.get("score") is not None else "–",
    )

    def fill(t: str) -> str:
        return _fill(t, fmt)

    txt = {k: fill(layout["texts"].get(k, v[1])) for k, v in TEXTS.items()}

    return {
        "txt": txt, "md": md_html, "d": detail, "layout": layout, "accent_dark": darken(layout["accent"]), "title": fill(layout["title"]), "subtitle": fill(layout["subtitle"]),
        "overall": overall, "overall_prev": prev, "overall_company": comp,
        "strengths": ordered[:2], "growth": list(reversed(ordered))[:2], "dims": ordered,
        "sections": [dict(s, title=fill(s["title"]), body=fill(s.get("body", ""))) for s in layout["sections"] if s["enabled"] and _has_data(s["key"], detail)],
        "f": _f, "choice_label": choice_label,
    }


def _has_data(key: str, d: dict) -> bool:
    return {
        "summary": bool(d.get("dimensions")), "highlights": bool(d.get("dimensions")), "dimensions": bool(d.get("dimensions")),
        "questions": bool(d.get("questions")), "nps": bool(d.get("nps") and d["nps"].get("n")),
        "choices": any(q.get("type") == "choice" for q in d.get("questions") or []),
        "ai_summary": bool(d.get("ai_summary")), "categories": bool(d.get("categories")),
        "wordcloud": bool(d.get("wordcloud")), "freetext": bool(d.get("freetext")), "guide": True,
    }.get(key, key.startswith("custom:"))


_HTML = """<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 18mm 15mm 18mm 15mm; @bottom-center { content: "{{ layout.footer|e }} · Seite " counter(page); font-size: 8pt; color: #666; } }
body{font-family:'DejaVu Sans',sans-serif;font-size:10pt;color:#1e2333}
h1{color:{{ accent_dark }};font-size:20pt;margin:0 0 2mm}h2{color:{{ accent_dark }};font-size:13pt;border-bottom:2px solid {{ layout.accent }};padding-bottom:1mm;margin-top:8mm}
.sub{color:#555;margin:0 0 4mm}.intro{margin:3mm 0 4mm}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:3px 5px;text-align:left;font-size:9pt}th{background:#f1f2f8}
.bar{background:{{ layout.accent }};height:8px}.big{font-size:26pt;font-weight:bold;color:{{ accent_dark }}}
.good{color:#15803d}.bad{color:#b91c1c}.muted{color:#666;font-size:8.5pt}.cols{width:100%}.cols td{border:0;vertical-align:top;width:50%}
.custom p,.closing p{margin:2mm 0}.closing{margin-top:8mm;border-top:1px solid #ccc;padding-top:3mm}.tag{display:inline-block;padding:1px 6px;margin:1px;border:1px solid #ccc;border-radius:8px;font-size:9pt}
</style></head><body>
<h1>{{ title }}</h1><p class="sub">{{ subtitle }}</p>
{% if layout.intro %}<p class="intro">{{ layout.intro }}</p>{% endif %}
{% for s in sections %}
{% if s.key == 'summary' %}<h2>{{ s.title }}</h2>
<p><span class="big">{{ f(overall) }}</span> {{ txt.summary_scale }}
{% if overall_prev is not none %} · {{ '▲' if overall >= overall_prev else '▼' }} {{ f(overall - overall_prev) }} {{ txt.summary_prev }}{% endif %}
{% if overall_company is not none %} · {{ '▲' if overall >= overall_company else '▼' }} {{ f(overall - overall_company) }} {{ txt.summary_company }} (Ø {{ f(overall_company) }}){% endif %}
· {{ d.n_responses }} {{ txt.summary_responses }}</p>
{% elif s.key == 'highlights' %}<h2>{{ s.title }}</h2>
<table class="cols"><tr><td><b class="good">▲ {{ txt.good_label }}</b><br>{% for x in strengths %}{{ x.dimension }}: {{ f(x.mean) }}<br>{% endfor %}</td>
<td><b class="bad">▼ {{ txt.growth_label }}</b><br>{% for x in growth %}{{ x.dimension }}: {{ f(x.mean) }}<br>{% endfor %}</td></tr></table>
{% elif s.key == 'dimensions' %}<h2>{{ s.title }}</h2>
<table><tr><th>Thema</th><th>Ø</th>{% if layout.columns.median %}<th>Median</th>{% endif %}{% if layout.columns.stddev %}<th>Std.abw.</th>{% endif %}{% if layout.columns.minmax %}<th>Min/Max</th>{% endif %}
{% if layout.columns.fachbereich %}<th>Fachbereich</th>{% endif %}{% if layout.columns.unternehmen %}<th>Unternehmen</th>{% endif %}{% if layout.columns.vorrunde %}<th>Vorrunde</th>{% endif %}</tr>
{% for x in dims %}<tr><td>{{ x.dimension }}</td><td>{{ f(x.mean) }}<div class="bar" style="width:{{ ((x.mean - 1) / 4 * 100)|round }}%"></div></td>
{% if layout.columns.median %}<td>{{ f(x.median, 1) }}</td>{% endif %}{% if layout.columns.stddev %}<td>{{ f(x.stddev) }}</td>{% endif %}{% if layout.columns.minmax %}<td>{{ x.min }}/{{ x.max }}</td>{% endif %}
{% if layout.columns.fachbereich %}<td>{{ f(x.fachbereich.mean) if x.fachbereich else '–' }}</td>{% endif %}
{% if layout.columns.unternehmen %}<td>{{ f(x.unternehmen.mean) if x.unternehmen else '–' }}</td>{% endif %}
{% if layout.columns.vorrunde %}<td>{{ f(x.vorrunde.mean) if x.vorrunde else '–' }}</td>{% endif %}</tr>{% endfor %}</table>
{% elif s.key == 'questions' %}<h2>{{ s.title }}</h2><table><tr><th>Frage</th><th>n</th><th>Ergebnis</th></tr>
{% for q in d.questions %}<tr><td>{{ q.question }}</td><td>{{ q.n }}</td><td>
{% if q.type == 'choice' %}{% for k, v in q.distribution.items() %}{{ choice_label(q, k) }}: {{ v }}{% if not loop.last %} · {% endif %}{% endfor %}
{% elif q.type == 'nps' %}NPS {{ q.nps.score if q.nps else '–' }}{% else %}Ø {{ f(q.mean) }}{% endif %}</td></tr>{% endfor %}</table>
{% elif s.key == 'nps' %}<h2>{{ s.title }}</h2><p><span class="big">{{ d.nps.score }}</span> · {{ d.nps.promoters }} Fans, {{ d.nps.passives }} Neutrale, {{ d.nps.detractors }} Kritiker
{% if d.nps_reference and d.nps_reference.value is not none %}· Referenz „{{ d.nps_reference.label }}“: {{ d.nps_reference.value }}{% endif %}</p>
{% elif s.key == 'choices' %}<h2>{{ s.title }}</h2>
{% for q in d.questions if q.type == 'choice' %}<p><b>{{ q.question }}</b> <span class="muted">({{ q.n }} Antworten)</span></p><table>
{% for k, v in q.distribution.items() %}<tr><td style="width:40%">{{ choice_label(q, k) }}</td><td>{{ v }}<div class="bar" style="width:{{ (v / q.n * 100)|round if q.n else 0 }}%"></div></td></tr>{% endfor %}</table>{% endfor %}
{% elif s.key == 'ai_summary' %}<h2>{{ s.title }}</h2><p>{{ d.ai_summary }}</p>
{% elif s.key == 'categories' %}<h2>{{ s.title }}</h2>{% for c in d.categories %}<p><b>{{ c.category }}</b> ({{ c.count }})</p><ul>{% for t in c.texts %}<li>{{ t }}</li>{% endfor %}</ul>{% endfor %}{% if txt.freetext_note %}<p class="muted">{{ txt.freetext_note }}</p>{% endif %}
{% elif s.key == 'wordcloud' %}<h2>{{ s.title }}</h2><p>{% for w in d.wordcloud %}<span class="tag" style="font-size:{{ 8 + [w.count, 8]|min * 1.5 }}pt">{{ w.word }}</span>{% endfor %}</p>
{% elif s.key == 'freetext' %}<h2>{{ s.title }}</h2>{% for g in d.freetext %}<p><b>{{ g.question }}</b></p><ul>{% for t in g.texts %}<li>{{ t }}</li>{% endfor %}</ul>{% endfor %}{% if txt.freetext_note %}<p class="muted">{{ txt.freetext_note }}</p>{% endif %}
{% elif s.key == 'guide' %}<h2>{{ s.title }}</h2><div class="muted">{{ md(txt.guide_body) }}</div>
{% elif s.key.startswith('custom:') %}<h2>{{ s.title }}</h2><div class="custom">{{ md(s.body) }}</div>
{% endif %}
{% endfor %}
{% if txt.closing %}<div class="closing">{{ md(txt.closing) }}</div>{% endif %}
</body></html>"""

_env = Environment(autoescape=True)
_tpl = _env.from_string(_HTML)


def render_html(detail: dict, layout: dict) -> str:
    return _tpl.render(**prepare(detail, layout))


# ---------------------------------------------------------------- PowerPoint
def build_pptx(detail: dict, layout: dict) -> bytes:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt

    ctx = prepare(detail, layout)
    acc = RGBColor.from_string(ctx["layout"]["accent"].lstrip("#").upper())
    acc_text = RGBColor.from_string(ctx["accent_dark"].lstrip("#").upper())
    dark = RGBColor(0x17, 0x24, 0x1B)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    def text(slide, t, x, y, w, h, size=18, bold=False, color=dark):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, line in enumerate(str(t).split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size, p.font.bold, p.font.color.rgb = Pt(size), bold, color
        return tb

    def new_slide(title):
        s = prs.slides.add_slide(blank)
        bar = s.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.25))
        bar.fill.solid()
        bar.fill.fore_color.rgb = acc
        bar.line.fill.background()
        text(s, title, 0.6, 0.45, 12, 0.9, 30, True, acc_text)
        text(s, ctx["layout"]["footer"], 0.6, 7.0, 12, 0.4, 10, False, RGBColor(0x66, 0x66, 0x66))
        return s

    def table(slide, header, rows, x, y, w, col_w=None):
        shape = slide.shapes.add_table(len(rows) + 1, len(header), Inches(x), Inches(y), Inches(w), Inches(0.4 * (len(rows) + 1)))
        t = shape.table
        for c, h in enumerate(header):
            t.cell(0, c).text = str(h)
        for r, row in enumerate(rows, start=1):
            for c, v in enumerate(row):
                t.cell(r, c).text = str(v)
        for r in range(len(rows) + 1):
            for c in range(len(header)):
                for p in t.cell(r, c).text_frame.paragraphs:
                    p.font.size = Pt(13)
        return t

    # Titelfolie
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = acc
    bg.line.fill.background()
    text(s, ctx["title"], 0.8, 2.4, 11.5, 1.6, 40, True, dark)
    text(s, ctx["subtitle"] + (("\n" + ctx["layout"]["intro"]) if ctx["layout"]["intro"] else ""), 0.8, 4.2, 11.5, 1.5, 20, False, dark)

    d, f = ctx["d"], _f
    for sec in ctx["sections"]:
        k, title = sec["key"], sec["title"]
        if k == "summary":
            s = new_slide(title)
            text(s, f(ctx["overall"], 1), 0.8, 1.7, 4, 2, 90, True, acc_text)
            text(s, ctx["txt"]["summary_scale"], 4.2, 3.0, 2.6, 0.8, 24)
            lines = []
            if ctx["overall_prev"] is not None:
                lines.append(f"{'▲' if ctx['overall'] >= ctx['overall_prev'] else '▼'} {f(ctx['overall'] - ctx['overall_prev'], 1)} {ctx['txt']['summary_prev']}")
            if ctx["overall_company"] is not None:
                lines.append(f"{'▲' if ctx['overall'] >= ctx['overall_company'] else '▼'} {f(ctx['overall'] - ctx['overall_company'], 1)} {ctx['txt']['summary_company']} (Ø {f(ctx['overall_company'], 1)})")
            lines.append(f"{d.get('n_responses', 0)} {ctx['txt']['summary_responses']}")
            text(s, "\n".join(lines), 7, 2.0, 5.8, 3, 22)
        elif k == "highlights":
            s = new_slide(title)
            text(s, "▲ " + ctx["txt"]["good_label"] + "\n" + "\n".join(f"{x['dimension']}: {f(x['mean'], 1)}" for x in ctx["strengths"]), 0.8, 1.8, 5.8, 3, 24, False, RGBColor(0x15, 0x80, 0x3D))
            text(s, "▼ " + ctx["txt"]["growth_label"] + "\n" + "\n".join(f"{x['dimension']}: {f(x['mean'], 1)}" for x in ctx["growth"]), 7, 1.8, 5.8, 3, 24, False, RGBColor(0xB9, 0x1C, 0x1C))
        elif k == "dimensions":
            s = new_slide(title)
            cd = CategoryChartData()
            cd.categories = [x["dimension"] for x in ctx["dims"]]
            cd.add_series("Ich", [round(x["mean"], 2) for x in ctx["dims"]])
            cols = ctx["layout"]["columns"]
            if cols["fachbereich"] and all(x.get("fachbereich") for x in ctx["dims"]):
                cd.add_series("Fachbereich", [round(x["fachbereich"]["mean"], 2) for x in ctx["dims"]])
            if cols["unternehmen"] and all(x.get("unternehmen") for x in ctx["dims"]):
                cd.add_series("Unternehmen", [round(x["unternehmen"]["mean"], 2) for x in ctx["dims"]])
            if cols["vorrunde"] and all(x.get("vorrunde") for x in ctx["dims"]):
                cd.add_series("Vorrunde", [round(x["vorrunde"]["mean"], 2) for x in ctx["dims"]])
            gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.4), Inches(12), Inches(5.5), cd)
            ch = gf.chart
            ch.has_legend = True
            ch.legend.position = XL_LEGEND_POSITION.BOTTOM
            ch.legend.include_in_layout = False
            ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 1, 5
            ch.plots[0].has_data_labels = True
            ch.plots[0].data_labels.font.size = Pt(11)
            ch.plots[0].data_labels.number_format = "0.0"
            ch.plots[0].data_labels.number_format_is_linked = False
            ch.series[0].format.fill.solid()
            ch.series[0].format.fill.fore_color.rgb = acc
        elif k == "questions":
            s = new_slide(title)
            rows = []
            for q in (d.get("questions") or [])[:12]:
                res = ("NPS " + str((q.get("nps") or {}).get("score", "–"))) if q["type"] == "nps" else ("siehe Auswahlfragen" if q["type"] == "choice" else "Ø " + f(q.get("mean"), 1))
                rows.append([q["question"][:90], q["n"], res])
            table(s, ["Frage", "n", "Ergebnis"], rows, 0.6, 1.4, 12)
        elif k == "nps":
            s = new_slide(title)
            n = d["nps"]
            text(s, str(n["score"]), 0.8, 1.7, 4, 2, 90, True, acc_text)
            text(s, f"{n['promoters']} Fans · {n['passives']} Neutrale · {n['detractors']} Kritiker\n" + (f"Referenz „{d['nps_reference']['label']}“: {d['nps_reference']['value']}" if d.get("nps_reference") and d["nps_reference"].get("value") is not None else ""), 6, 2.2, 6.8, 3, 22)
        elif k == "choices":
            for q in [q for q in d.get("questions") or [] if q["type"] == "choice"]:
                s = new_slide(title)
                text(s, q["question"], 0.6, 1.3, 12, 0.8, 18)
                cd = CategoryChartData()
                cd.categories = [choice_label(q, key) for key in q["distribution"]]
                cd.add_series("Antworten", list(q["distribution"].values()))
                gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(2.1), Inches(12), Inches(4.8), cd)
                gf.chart.has_legend = False
                gf.chart.plots[0].has_data_labels = True
                gf.chart.series[0].format.fill.solid()
                gf.chart.series[0].format.fill.fore_color.rgb = acc
        elif k == "ai_summary":
            s = new_slide(title)
            text(s, d["ai_summary"], 0.8, 1.6, 11.8, 5, 22)
        elif k in ("categories", "freetext"):
            groups = [(c["category"], c["texts"]) for c in d.get("categories") or []] if k == "categories" else [(g["question"], g["texts"]) for g in d.get("freetext") or []]
            for name, texts in groups:
                for i in range(0, len(texts), 6):
                    s = new_slide(f"{title}: {name}" if i == 0 else f"{title}: {name} (Forts.)")
                    text(s, "\n".join("• " + t for t in texts[i:i + 6]), 0.8, 1.6, 11.8, 5, 18)
        elif k == "wordcloud":
            s = new_slide(title)
            text(s, "  ·  ".join(f"{w['word']} ({w['count']})" for w in d.get("wordcloud") or []), 0.8, 1.8, 11.8, 4, 24, False, acc_text)
        elif k == "guide":
            s = new_slide(title)
            text(s, "\n".join(md_lines(ctx["txt"]["guide_body"])), 0.8, 1.8, 11.8, 4, 22)
        elif k.startswith("custom:"):
            s = new_slide(title)
            text(s, "\n".join(md_lines(sec["body"])), 0.8, 1.6, 11.8, 5, 22)
    if ctx["txt"]["closing"]:
        s = new_slide("")
        text(s, "\n".join(md_lines(ctx["txt"]["closing"])), 0.8, 2.4, 11.8, 3.5, 24)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- Excel / CSV
def _tables(detail: dict, layout: dict) -> list[tuple[str, list[str], list[list]]]:
    ctx = prepare(detail, layout)
    d = ctx["d"]
    keys = {s["key"] for s in ctx["sections"]}
    out = [("Überblick", ["Kennzahl", "Wert"], [
        ["Runde", d.get("round_name", "")], ["Antworten", d.get("n_responses", 0)],
        ["Gesamtwert (Ø)", round(ctx["overall"], 2) if ctx["overall"] is not None else ""],
        ["Vorrunde (Ø)", round(ctx["overall_prev"], 2) if ctx["overall_prev"] is not None else ""],
        ["Unternehmen (Ø)", round(ctx["overall_company"], 2) if ctx["overall_company"] is not None else ""],
    ])]
    if d.get("dimensions"):
        out.append(("Themen", ["Thema", "Mittelwert", "Median", "Std.abw.", "Min", "Max", "n", "Fachbereich", "Unternehmen", "Vorrunde"], [
            [x["dimension"], x["mean"], x["median"], x["stddev"], x["min"], x["max"], x["n"],
             (x.get("fachbereich") or {}).get("mean", ""), (x.get("unternehmen") or {}).get("mean", ""), (x.get("vorrunde") or {}).get("mean", "")]
            for x in ctx["dims"]]))
    if d.get("questions"):
        rows = []
        for q in d["questions"]:
            if q["type"] == "choice":
                rows += [[q["question"], "Auswahl", choice_label(q, k), v, q["n"]] for k, v in q["distribution"].items()]
            else:
                rows.append([q["question"], q["type"], "Ø" if q["type"] != "nps" else "NPS", q.get("mean") if q["type"] != "nps" else (q.get("nps") or {}).get("score", ""), q["n"]])
        out.append(("Fragen", ["Frage", "Typ", "Merkmal", "Wert", "n"], rows))
    if d.get("nps") and d["nps"].get("n"):
        n = d["nps"]
        out.append(("NPS", ["Merkmal", "Wert"], [["NPS", n["score"]], ["Fans", n["promoters"]], ["Neutrale", n["passives"]], ["Kritiker", n["detractors"]]]))
    if "categories" in keys:
        out.append(("Themen Freitext", ["Kategorie", "Anzahl"], [[c["category"], c["count"]] for c in d.get("categories") or []]))
    if "freetext" in keys:
        out.append(("Freitexte", ["Frage", "Text"], [[g["question"], t] for g in d.get("freetext") or [] for t in g["texts"]]))
    return out


def build_xlsx(detail: dict, layout: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    acc = normalize(layout)["accent"].lstrip("#").upper()
    wb = Workbook()
    wb.remove(wb.active)
    for name, header, rows in _tables(detail, layout):
        ws = wb.create_sheet(name[:31])
        ws.append(header)
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="10231A"), PatternFill("solid", fgColor=acc)
        for r in rows:
            ws.append(r)
        for i, col in enumerate(ws.columns, start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(70, max(12, max(len(str(c.value or "")) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_csv(detail: dict, layout: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    for name, header, rows in _tables(detail, layout):
        w.writerow([f"# {name}"])
        w.writerow(header)
        for r in rows:
            w.writerow([str(v).replace(".", ",") if isinstance(v, float) else v for v in r])
        w.writerow([])
    return "﻿" + buf.getvalue()
