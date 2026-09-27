const pptxgen = require("pptxgenjs");

// ---------------------------------------------------------------- Palette
// Markenfarben der Plattform: Waldgruen (dominant) + Petrol (sekundaer),
// plus ein scharfer Warnakzent nur fuer die Anonymitaets-Regeln.
const FOREST = "004F23";
const FOREST_DARK = "013219"; // dunklere Buehne fuer Titel/Abschluss/Regeln
const FOREST_LIGHT = "E6F1EA"; // helle Flaeche fuer Chips/Karten
const PETROL = "007298";
const PETROL_LIGHT = "DCEFF4";
const INK = "10231B"; // Fliesstext auf hellem Grund
const INK_SOFT = "44584F";
const PAPER = "FFFFFF";
const MINT_MUTE = "BFE3D2"; // Text auf dunklem Grund (gedaempft)
const WARN = "B3402A";

const HEAD = "Cambria";
const BODY = "Calibri";

const pptx = new pptxgen();
pptx.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
pptx.layout = "WIDE";
const W = 13.333, H = 7.5;

// ---------------------------------------------------------------- Helfer
function darkBg(slide, { circle = true } = {}) {
  slide.background = { color: FOREST_DARK };
  if (circle) {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: W - 4.6, y: H - 5.4, w: 9, h: 9, fill: { color: PETROL, transparency: 82 }, line: { type: "none" },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: -3.2, y: -3.6, w: 5.5, h: 5.5, fill: { color: FOREST, transparency: 55 }, line: { type: "none" },
    });
  }
}

function eyebrow(slide, text, opts = {}) {
  slide.addText(text.toUpperCase(), {
    x: opts.x ?? 0.7, y: opts.y ?? 0.45, w: opts.w ?? 8, h: 0.4,
    fontFace: BODY, fontSize: 12, bold: true, color: opts.color ?? PETROL, charSpacing: 2,
    isTextBox: true, margin: 0,
  });
}

function title(slide, text, opts = {}) {
  slide.addText(text, {
    x: opts.x ?? 0.7, y: opts.y ?? 0.82, w: opts.w ?? 11.9, h: opts.h ?? 0.9,
    fontFace: HEAD, fontSize: opts.size ?? 32, bold: true, color: opts.color ?? FOREST_DARK,
    isTextBox: true, margin: 0, valign: "top",
  });
}

function badge(slide, x, y, d, label, opts = {}) {
  const bg = opts.bg ?? FOREST;
  const fg = opts.fg ?? PAPER;
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: bg }, line: { type: "none" } });
  slide.addText(String(label), {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: BODY, fontSize: opts.fontSize ?? 16, bold: true, color: fg, isTextBox: true, margin: 0,
  });
}

// Kachel: nummerierte Chip-Kachel mit fettem Titel + Beschreibung (Wiederholmotiv)
function featureCard(slide, x, y, w, h, num, head, body, opts = {}) {
  const accent = opts.accent ?? FOREST;
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.09,
    fill: { color: opts.cardFill ?? PAPER }, line: { color: "E1E8E3", width: 1 },
    shadow: { type: "outer", color: "1B2E24", opacity: 0.14, blur: 10, offset: 3, angle: 90 },
  });
  badge(slide, x + 0.22, y + 0.22, 0.5, num, { bg: accent, fontSize: 16 });
  slide.addText(head, {
    x: x + 0.9, y: y + 0.2, w: w - 1.1, h: 0.4, fontFace: BODY, fontSize: 15, bold: true, color: INK,
    isTextBox: true, margin: 0, valign: "top",
  });
  slide.addText(body, {
    x: x + 0.9, y: y + 0.58, w: w - 1.1, h: h - 0.72, fontFace: BODY, fontSize: 12.5, color: INK_SOFT,
    isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.12,
  });
}

function footer(slide, n) {
  slide.addText("Führungsfeedback-Portal", {
    x: 0.7, y: H - 0.5, w: 6, h: 0.3, fontFace: BODY, fontSize: 9, color: "8FA79C", isTextBox: true, margin: 0,
  });
  slide.addText(String(n), {
    x: W - 1.2, y: H - 0.5, w: 0.6, h: 0.3, align: "right", fontFace: BODY, fontSize: 9, color: "8FA79C",
    isTextBox: true, margin: 0,
  });
}

function lightSlide() {
  const s = pptx.addSlide();
  s.background = { color: PAPER };
  return s;
}

// ================================================================== 1. Titel
{
  const s = pptx.addSlide();
  darkBg(s);
  eyebrow(s, "Führungsfeedback-Portal", { color: "8FD9C9", y: 2.55 });
  s.addText("Anonymes 360°-Feedback\nfür Führungskräfte", {
    x: 0.8, y: 2.95, w: 10.8, h: 2.1, fontFace: HEAD, fontSize: 44, bold: true, color: PAPER,
    isTextBox: true, margin: 0, lineSpacingMultiple: 1.05,
  });
  s.addText("Funktionsüberblick und technische Architektur", {
    x: 0.82, y: 4.95, w: 9, h: 0.6, fontFace: BODY, fontSize: 19, color: MINT_MUTE, isTextBox: true, margin: 0,
  });
  s.addText("Interne Vorstellung", {
    x: 0.82, y: H - 0.75, w: 6, h: 0.4, fontFace: BODY, fontSize: 11, color: "6FA08F", isTextBox: true, margin: 0,
  });
}

// ================================================================== 2. Ausgangslage
{
  const s = lightSlide();
  eyebrow(s, "Was ist das Führungsfeedback-Portal");
  title(s, "Anonymes Feedback, das wirklich ankommt");
  s.addText(
    "Mitarbeitende bewerten halbjährlich anonym ihre direkte Führungskraft. Führungskräfte bewerten wiederum ihre eigene Führungskraft. " +
    "Aus den Antworten entsteht automatisch ein Report je Führungskraft — erst ab drei Antworten, damit niemand Rückschlüsse auf eine " +
    "einzelne Person ziehen kann. HR behält Organisation, Umfrage-Inhalte und Rücklauf im Blick.",
    { x: 0.7, y: 2.05, w: 6.7, h: 3.6, fontFace: BODY, fontSize: 15, color: INK_SOFT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.3 }
  );

  const stats = [["3", "Rollen: Mitarbeiter, Führungskraft, Admin"], ["≥ 3", "Antworten, bevor ein Report entsteht"],
                 ["20", "Sprachen je Fragebogen wählbar"], ["4", "Export-Formate: PDF, PowerPoint, Excel, CSV"]];
  const gx = 7.85, gy = 2.05, gw = 4.75, gh = 1.68, gap = 0.24;
  stats.forEach(([num, label], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = gx + col * (gw / 2 + gap / 2), y = gy + row * (gh + gap);
    s.addShape(pptx.ShapeType.roundRect, {
      x, y, w: gw / 2 - gap / 2, h: gh, rectRadius: 0.09, fill: { color: FOREST_LIGHT }, line: { type: "none" },
    });
    s.addText(num, { x: x + 0.22, y: y + 0.18, w: gw / 2 - gap / 2 - 0.4, h: 0.7, fontFace: HEAD, fontSize: 30, bold: true, color: FOREST, isTextBox: true, margin: 0 });
    s.addText(label, { x: x + 0.22, y: y + 0.88, w: gw / 2 - gap / 2 - 0.4, h: gh - 0.98, fontFace: BODY, fontSize: 11.5, color: INK_SOFT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15 });
  });
  footer(s, 2);
}

// ================================================================== 3. So funktioniert es
{
  const s = lightSlide();
  eyebrow(s, "Ablauf");
  title(s, "So funktioniert es");
  const steps = [
    ["Runde anlegen", "HR wählt Fragebogen & Zeitraum — einmalig oder automatisch wiederkehrend."],
    ["Anonym bewerten", "Mitarbeitende füllen den Fragebogen aus — am Handy, Tablet oder PC."],
    ["Report entsteht", "Ab drei Antworten wertet das System automatisch aus und schwärzt Freitexte."],
    ["Maßnahmen ableiten", "Führungskraft sieht den Report und leitet Maßnahmen fürs Team ab."],
  ];
  const cw = 2.78, ch = 3.9, gap = 0.28, startX = 0.7, y0 = 2.35;
  steps.forEach(([h, b], i) => {
    const x = startX + i * (cw + gap);
    s.addShape(pptx.ShapeType.roundRect, {
      x, y: y0, w: cw, h: ch, rectRadius: 0.1, fill: { color: i % 2 === 0 ? FOREST_LIGHT : PETROL_LIGHT }, line: { type: "none" },
    });
    badge(s, x + 0.28, y0 + 0.3, 0.62, i + 1, { bg: i % 2 === 0 ? FOREST : PETROL, fontSize: 20 });
    s.addText(h, { x: x + 0.28, y: y0 + 1.15, w: cw - 0.56, h: 0.7, fontFace: HEAD, fontSize: 17, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(b, { x: x + 0.28, y: y0 + 1.85, w: cw - 0.56, h: ch - 2.05, fontFace: BODY, fontSize: 12, color: INK_SOFT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.2 });
    if (i < steps.length - 1) {
      s.addText("→", { x: x + cw, y: y0 + ch / 2 - 0.35, w: gap, h: 0.7, align: "center", valign: "middle", fontFace: BODY, fontSize: 22, bold: true, color: "9DB0A6", isTextBox: true, margin: 0 });
    }
  });
  footer(s, 3);
}

// ------------------------------------------------------------ Icon-Grid-Slide (wiederverwendet)
function grid2x2Slide(n, tag, tagColor, heading, items, accent) {
  const s = lightSlide();
  eyebrow(s, tag, { color: tagColor });
  title(s, heading);
  const cw = 5.75, ch = 2.05, gapX = 0.4, gapY = 0.28, x0 = 0.7, y0 = 2.15;
  items.forEach(([h, b], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = x0 + col * (cw + gapX), y = y0 + row * (ch + gapY);
    featureCard(s, x, y, cw, ch, i + 1, h, b, { accent });
  });
  footer(s, n);
  return s;
}

// ================================================================== 4. Mitarbeitende
grid2x2Slide(4, "Für Mitarbeitende", FOREST, "Feedback geben, im Blick behalten", [
  ["Ein Dashboard, eine Aufgabe", "„Du hast 2 offene Feedbacks“ oder „Alles erledigt“ — mit Fälligkeitsdatum."],
  ["Feedback in ca. 5 Minuten", "Große Antwort-Kacheln, funktioniert auf Handy, Tablet und Kiosk-PC."],
  ["Vertrauens-Hinweis", "Vor jeder Umfrage steht in Klartext, was mit den Antworten passiert."],
  ["Eigene Antworten ansehen", "Nach der Abgabe nur lesbar und nur auf dem eigenen Gerät gespeichert."],
], FOREST);

// ================================================================== 5. Führungskräfte
grid2x2Slide(5, "Für Führungskräfte", PETROL, "Den eigenen Report verstehen und nutzen", [
  ["Report in vier Reitern", "Überblick, Themen im Detail, Freitexte, Verlauf über mehrere Runden."],
  ["Einordnung auf einen Blick", "Vergleich mit Fachbereich, Unternehmen und Vorrunde; Ampel-Bewertung."],
  ["Weiterempfehlung (NPS)", "Würde mich mein Team weiterempfehlen? Mit Referenzwert."],
  ["Export & Maßnahmen", "Als PDF, PowerPoint, Excel oder CSV — plus Maßnahmen fürs Team ableiten."],
], PETROL);

// ================================================================== 6. Admin: Umfrage & Runden
grid2x2Slide(6, "Für HR / Admin", FOREST, "Umfrage gestalten & Befragungsrunden", [
  ["Vier Fragetypen", "Likert-Skala, Weiterempfehlung (NPS), Auswahl, Freitext — mit Verzweigungen."],
  ["Mehrsprachig", "Beliebige Zusatzsprachen; fehlende Texte fallen auf Deutsch zurück."],
  ["Automatisch wiederkehrend", "Vierteljährlich, halbjährlich oder jährlich — läuft von selbst."],
  ["Teams immer aktuell", "Vor jedem Rundenstart automatisch aus SAP aktualisiert."],
], FOREST);

// ================================================================== 7. Admin: Auswertung & Rechte
grid2x2Slide(7, "Für HR / Admin", PETROL, "Auswertung, Reports & Rechte", [
  ["Pseudonymer Benchmark", "Führungskräfte vergleichen — als „FK-A“, „FK-B“, nie mit echtem Namen."],
  ["Unternehmensweiter NPS", "Mit manuell pflegbarem Referenzwert, z. B. aus einer Branchenstudie."],
  ["Eigenes Report-Layout", "Abschnitte, Textbausteine und Platzhalter zentral festlegen."],
  ["Feine Zugriffsrollen", "z. B. „nur Auswertung ansehen“ statt Vollzugriff für alle Admins."],
], PETROL);

// ================================================================== 8. Anonymitaet
{
  const s = pptx.addSlide();
  darkBg(s, { circle: false });
  s.addShape(pptx.ShapeType.ellipse, { x: W - 3.4, y: -2.2, w: 6, h: 6, fill: { color: FOREST, transparency: 55 }, line: { type: "none" } });
  eyebrow(s, "Grundprinzip der Plattform", { color: "8FD9C9" });
  title(s, "Anonymität & Sicherheit", { color: PAPER, w: 8.5 });
  s.addShape(pptx.ShapeType.roundRect, {
    x: W - 3.75, y: 0.42, w: 3.05, h: 0.42, rectRadius: 0.21, fill: { color: WARN }, line: { type: "none" },
  });
  s.addText("NICHT VERHANDELBAR", {
    x: W - 3.75, y: 0.42, w: 3.05, h: 0.42, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 11.5, bold: true, color: PAPER, charSpacing: 1, isTextBox: true, margin: 0,
  });

  const rules = [
    ["Team-Schwelle", "Eine Führungskraft wird nur bewertet, wenn ihr Team mindestens drei Personen hat."],
    ["Berichts-Schwelle", "Ein Report erscheint erst ab drei abgegebenen Antworten — auf jeder Ebene."],
    ["Getrennte Systeme", "Jede Führungskraft bekommt je Runde eine eigene Umfrage. Das Portal weiß nur „teilgenommen“, nie „was geantwortet“."],
    ["Keine Rohantworten für Admins", "Auch HR sieht niemals eine einzelne Antwort mit Personenbezug."],
    ["Eigene Antworten", "Nur als schreibgeschützte Kopie auf dem eigenen Gerät — nie auf dem Server."],
  ];
  let y = 2.05;
  const rh = 0.92;
  rules.forEach(([h, b], i) => {
    badge(s, 0.75, y + 0.05, 0.42, "✓", { bg: PETROL, fg: PAPER, fontSize: 15 });
    s.addText([{ text: h + "  ", options: { bold: true, color: PAPER } }, { text: b, options: { color: MINT_MUTE } }], {
      x: 1.35, y, w: 11.2, h: rh, fontFace: BODY, fontSize: 14, isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.2,
    });
    y += rh;
  });
  footer(s, 8);
}

// ================================================================== 9. Architektur
{
  const s = lightSlide();
  eyebrow(s, "Technische Seite");
  title(s, "Architektur im Überblick");
  s.addText("Das Feedback-Portal ist Eigenentwicklung und steuert Organisation, Rollen, Runden und Reports. LimeSurvey bleibt unverändert der reine „Umfrage-Motor“.", {
    x: 0.7, y: 1.65, w: 11.8, h: 0.5, fontFace: BODY, fontSize: 13.5, color: INK_SOFT, isTextBox: true, margin: 0,
  });

  const midY = 4.55, boxH = 0.85;
  function node(x, w, label, sub, fill, fg) {
    s.addShape(pptx.ShapeType.roundRect, { x, y: midY - boxH / 2, w, h: boxH, rectRadius: 0.08, fill: { color: fill }, line: { type: "none" } });
    s.addText(label, { x: x + 0.12, y: midY - boxH / 2 + 0.1, w: w - 0.24, h: 0.4, fontFace: BODY, fontSize: 12.5, bold: true, color: fg, isTextBox: true, margin: 0, align: "center" });
    s.addText(sub, { x: x + 0.12, y: midY - boxH / 2 + 0.46, w: w - 0.24, h: 0.35, fontFace: BODY, fontSize: 9.5, color: fg, isTextBox: true, margin: 0, align: "center" });
  }
  function arrow(x1, x2) {
    s.addShape(pptx.ShapeType.rightArrow, { x: x1, y: midY - 0.16, w: x2 - x1, h: 0.32, fill: { color: "B9C9C0" }, line: { type: "none" } });
  }

  const nx = [0.7, 3.05, 6.45, 9.85];
  const nw = [1.9, 2.9, 2.9, 2.78];
  node(nx[0], nw[0], "Nutzer", "MA · FK · HR", "EAF1EC", INK);
  // Portal-Container
  s.addShape(pptx.ShapeType.roundRect, { x: nx[1] - 0.18, y: midY - 1.55, w: nw[1] + 0.36, h: 3.1, rectRadius: 0.1, fill: { color: FOREST_LIGHT }, line: { color: FOREST, width: 1, dashType: "dash" } });
  s.addText("Feedback-Portal (Eigenentwicklung)", { x: nx[1] - 0.18, y: midY - 1.55 + 0.08, w: nw[1] + 0.36, h: 0.3, align: "center", fontFace: BODY, fontSize: 10, bold: true, color: FOREST, isTextBox: true, margin: 0 });
  node(nx[1], nw[1], "Portal-Web", "SvelteKit", FOREST, PAPER);
  s.addShape(pptx.ShapeType.roundRect, { x: nx[1], y: midY + 0.6, w: nw[1], h: 0.7, rectRadius: 0.08, fill: { color: PAPER }, line: { color: FOREST, width: 1 } });
  s.addText("PostgreSQL", { x: nx[1], y: midY + 0.66, w: nw[1], h: 0.3, align: "center", fontFace: BODY, fontSize: 11, bold: true, color: FOREST, isTextBox: true, margin: 0 });
  s.addText("Organisation · Runden · Reports", { x: nx[1], y: midY + 0.98, w: nw[1], h: 0.3, align: "center", fontFace: BODY, fontSize: 8.5, color: INK_SOFT, isTextBox: true, margin: 0 });

  node(nx[2], nw[2], "Portal-API", "FastAPI", FOREST, PAPER);
  s.addShape(pptx.ShapeType.roundRect, { x: nx[2], y: midY + 0.6, w: nw[2], h: 0.7, rectRadius: 0.08, fill: { color: PAPER }, line: { color: PETROL, width: 1 } });
  s.addText("SAP · Entra ID · Mail · KI", { x: nx[2], y: midY + 0.66, w: nw[2], h: 0.3, align: "center", fontFace: BODY, fontSize: 9.5, bold: true, color: PETROL, isTextBox: true, margin: 0 });
  s.addText("Organisation, Anmeldung, Versand, Zusammenfassung", { x: nx[2], y: midY + 0.98, w: nw[2], h: 0.35, align: "center", fontFace: BODY, fontSize: 8, color: INK_SOFT, isTextBox: true, margin: 0 });

  node(nx[3], nw[3], "LimeSurvey", "1 Umfrage je FK + Runde", PETROL, PAPER);
  s.addShape(pptx.ShapeType.roundRect, { x: nx[3], y: midY + 0.6, w: nw[3], h: 0.7, rectRadius: 0.08, fill: { color: PAPER }, line: { color: PETROL, width: 1 } });
  s.addText("MariaDB", { x: nx[3], y: midY + 0.66, w: nw[3], h: 0.3, align: "center", fontFace: BODY, fontSize: 11, bold: true, color: PETROL, isTextBox: true, margin: 0 });
  s.addText("Rohantworten, 90 Tage", { x: nx[3], y: midY + 0.98, w: nw[3], h: 0.3, align: "center", fontFace: BODY, fontSize: 8.5, color: INK_SOFT, isTextBox: true, margin: 0 });

  arrow(nx[0] + nw[0] + 0.05, nx[1] - 0.13);
  arrow(nx[1] + nw[1] + 0.13, nx[2] - 0.13);
  arrow(nx[2] + nw[2] + 0.13, nx[3] - 0.05);

  s.addText("Nur Portal-API spricht mit allen anderen Systemen — LimeSurvey bleibt im Kern unverändert.", {
    x: 0.7, y: 6.55, w: 11.8, h: 0.4, fontFace: BODY, fontSize: 11.5, italic: true, color: INK_SOFT, isTextBox: true, margin: 0,
  });
  footer(s, 9);
}

// ================================================================== 10. Stand
{
  const s = lightSlide();
  eyebrow(s, "Reifegrad");
  title(s, "Stand & nächste Schritte");
  s.addText("Ein funktionsfähiger Prototyp mit allen gezeigten Funktionen, automatisiert getestet und mit echten Testdaten durchgespielt — noch kein produktionsreifes System.", {
    x: 0.7, y: 1.65, w: 11.8, h: 0.55, fontFace: BODY, fontSize: 13.5, color: INK_SOFT, isTextBox: true, margin: 0,
  });

  function col(x, head, color, items, glyph) {
    s.addShape(pptx.ShapeType.roundRect, { x, y: 2.35, w: 5.75, h: 4.2, rectRadius: 0.1, fill: { color: color === FOREST ? FOREST_LIGHT : PETROL_LIGHT }, line: { type: "none" } });
    s.addText(head, { x: x + 0.35, y: 2.6, w: 5.05, h: 0.5, fontFace: HEAD, fontSize: 18, bold: true, color, isTextBox: true, margin: 0 });
    let y = 3.25;
    items.forEach((t) => {
      s.addText([{ text: glyph + "  ", options: { bold: true, color } }, { text: t, options: { color: INK } }], {
        x: x + 0.35, y, w: 5.05, h: 0.65, fontFace: BODY, fontSize: 13, isTextBox: true, margin: 0, lineSpacingMultiple: 1.15, valign: "top",
      });
      y += 0.72;
    });
  }
  col(0.7, "Bereits geprüft", FOREST, [
    "Alle Kernfunktionen automatisiert getestet",
    "Echte Runde mit echten Teilnahmen durchgespielt",
    "Anonymität direkt in der Datenbank kontrolliert",
    "Lasttest: 300 gleichzeitige Teilnahmen ohne Fehler",
  ], "✓");
  col(6.85, "Nächste Schritte", PETROL, [
    "Freigabe durch Betriebsrat & Datenschutz",
    "Anbindung an echtes SAP, Entra ID und Mailserver",
    "Produktionsserver mit HTTPS und Backups",
    "KI-Provider gegen ein echtes internes Gateway testen",
  ], "→");
  footer(s, 10);
}

// ================================================================== 11. Abschluss
{
  const s = pptx.addSlide();
  darkBg(s);
  s.addText("Vielen Dank", {
    x: 0.8, y: 2.9, w: 10, h: 1.3, fontFace: HEAD, fontSize: 44, bold: true, color: PAPER, isTextBox: true, margin: 0,
  });
  s.addText("Fragen und Rückmeldungen sind jederzeit willkommen.", {
    x: 0.82, y: 4.05, w: 9, h: 0.6, fontFace: BODY, fontSize: 18, color: MINT_MUTE, isTextBox: true, margin: 0,
  });
}

pptx.writeFile({ fileName: "../Fuehrungsfeedback-Portal-Vorstellung.pptx" }).then(() => console.log("written"));
