const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  ImageRun, PageBreak, Header, Footer, VerticalAlign, LevelFormat,
} = require("docx");

const GREEN = "4F8A58";
const GREEN_DARK = "1C2620";
const GREEN_SOFT = "EEF4EE";
const MUTED = "5B6960";
const RULE_RED = "A5432C";
const RULE_SOFT = "F7ECE9";
const ROLE_MA = "4F8A58";
const ROLE_FK = "2F7D8C";
const ROLE_ADMIN = "A3711F";

const FONT = "Calibri";
const FONT_HEAD = "Georgia";

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 420, after: 180 },
    border: { bottom: { color: GREEN, space: 6, style: BorderStyle.SINGLE, size: 8 } },
    children: [new TextRun({ text, font: FONT_HEAD, color: GREEN_DARK, size: 32, bold: true })],
  });
}

function eyebrow(text, color) {
  return new Paragraph({
    spacing: { before: 0, after: 60 },
    children: [new TextRun({ text: text.toUpperCase(), font: FONT, color: color || GREEN, size: 17, bold: true, characterSpacing: 20 })],
  });
}

function lede(text) {
  return new Paragraph({
    spacing: { after: 200 },
    children: [new TextRun({ text, font: FONT, color: MUTED, size: 22 })],
  });
}

function feature(title, desc) {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { after: 130 },
    children: [
      new TextRun({ text: title + " — ", font: FONT, color: GREEN_DARK, size: 22, bold: true }),
      new TextRun({ text: desc, font: FONT, color: MUTED, size: 22 }),
    ],
  });
}

function ruleItem(bold, rest) {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { after: 110 },
    children: [
      new TextRun({ text: bold + " ", font: FONT, color: GREEN_DARK, size: 22, bold: true }),
      new TextRun({ text: rest, font: FONT, color: GREEN_DARK, size: 22 }),
    ],
  });
}

function cell(text, opts) {
  opts = opts || {};
  return new TableCell({
    width: { size: opts.width || 3000, type: WidthType.DXA },
    shading: opts.shading ? { type: ShadingType.CLEAR, fill: opts.shading } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 90, bottom: 90, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, font: FONT, size: 20, bold: !!opts.bold, color: opts.color || GREEN_DARK })],
    })],
  });
}

const noBorder = { style: BorderStyle.SINGLE, size: 4, color: "D8E2D9" };
const tableBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder, insideHorizontal: noBorder, insideVertical: noBorder };

function statTile(num, label) {
  return new TableCell({
    width: { size: 2350, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
    margins: { top: 160, bottom: 160, left: 140, right: 140 },
    borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
    children: [
      new Paragraph({ children: [new TextRun({ text: num, font: FONT_HEAD, bold: true, size: 34, color: GREEN })] }),
      new Paragraph({ spacing: { before: 40 }, children: [new TextRun({ text: label, font: FONT, size: 17, color: MUTED })] }),
    ],
  });
}

function stepTile(num, title, desc) {
  return new TableCell({
    width: { size: 2350, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: GREEN_SOFT },
    margins: { top: 140, bottom: 140, left: 140, right: 140 },
    borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
    children: [
      new Paragraph({ children: [new TextRun({ text: num, font: FONT_HEAD, bold: true, size: 30, color: GREEN })] }),
      new Paragraph({ spacing: { before: 40 }, children: [new TextRun({ text: title, font: FONT, bold: true, size: 19, color: GREEN_DARK })] }),
      new Paragraph({ spacing: { before: 20 }, children: [new TextRun({ text: desc, font: FONT, size: 16, color: MUTED })] }),
    ],
  });
}

function roleTag(text, color) {
  return new Table({
    width: { size: 2600, type: WidthType.DXA },
    borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE } },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 2600, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: "FFFFFF" },
      borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
      margins: { top: 60, bottom: 60, left: 140, right: 140 },
      children: [new Paragraph({ children: [new TextRun({ text, font: FONT, bold: true, size: 16, color })] })],
    })] })],
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: GREEN_DARK } } },
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1100, bottom: 1100, left: 1100, right: 1100 } } },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "Führungsfeedback-Portal", font: FONT, size: 15, color: MUTED })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Interne Dokumentation · alle Beispieldaten sind fiktiv", font: FONT, size: 15, color: MUTED })],
      })] }),
    },
    children: [
      // ---------- Titel ----------
      new Paragraph({ spacing: { before: 1200 }, children: [] }),
      new Paragraph({
        children: [new TextRun({ text: "FÜHRUNGSFEEDBACK-PORTAL", font: FONT, bold: true, size: 20, color: GREEN, characterSpacing: 30 })],
      }),
      new Paragraph({
        spacing: { before: 220, after: 220 },
        children: [new TextRun({ text: "Anonymes 360°-Feedback für Führungskräfte", font: FONT_HEAD, bold: true, size: 56, color: GREEN_DARK })],
      }),
      new Paragraph({
        spacing: { after: 500 },
        children: [new TextRun({ text: "Funktionsüberblick und technische Architektur", font: FONT, size: 26, color: MUTED })],
      }),
      new Paragraph({
        spacing: { after: 1400 },
        children: [new TextRun({
          text: "Mitarbeitende bewerten halbjährlich anonym ihre direkte Führungskraft. Führungskräfte bewerten wiederum ihre eigene Führungskraft. Aus den Antworten entsteht automatisch ein Report je Führungskraft — erst ab drei Antworten, damit niemand Rückschlüsse auf eine einzelne Person ziehen kann. HR behält Organisation, Umfrage-Inhalte und Rücklauf im Blick.",
          font: FONT, size: 23, color: GREEN_DARK,
        })],
      }),
      new Table({
        width: { size: 9400, type: WidthType.DXA },
        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE } },
        rows: [new TableRow({ children: [
          statTile("3", "Rollen: Mitarbeiter, Führungskraft, Admin"),
          statTile("4", "Fragetypen inkl. Verzweigungen"),
          statTile("20", "Sprachen je Fragebogen wählbar"),
          statTile("4", "Report-Formate: PDF · PowerPoint · Excel · CSV"),
        ] })],
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Überblick ----------
      eyebrow("Was ist das Führungsfeedback-Portal"),
      h1("So funktioniert es"),
      lede("Vier Schritte von der geplanten Runde bis zur abgeleiteten Maßnahme."),
      new Table({
        width: { size: 9400, type: WidthType.DXA },
        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE } },
        rows: [new TableRow({ children: [
          stepTile("1", "Runde anlegen", "HR wählt Fragebogen & Zeitraum — einmalig oder automatisch wiederkehrend."),
          stepTile("2", "Anonym bewerten", "Mitarbeitende füllen den Fragebogen aus — am Handy, Tablet oder PC."),
          stepTile("3", "Report entsteht", "Ab drei Antworten wertet das System automatisch aus und schwärzt Freitexte."),
          stepTile("4", "Maßnahmen ableiten", "Führungskraft sieht den Report und leitet Maßnahmen fürs Team ab."),
        ] })],
      }),
      new Paragraph({ spacing: { after: 200 } }),

      // ---------- Mitarbeitende ----------
      roleTag("FÜR MITARBEITENDE", ROLE_MA),
      h1("Feedback geben, im Blick behalten"),
      lede("Die Ansicht für alle: schnell verständlich, wenige Klicks, auf jedem Gerät."),
      feature("Ein Dashboard, eine Aufgabe", "„Du hast 2 offene Feedbacks“ oder „Alles erledigt“ — mit Fälligkeitsdatum, ohne Umwege."),
      feature("Feedback in ca. 5 Minuten", "Große Antwort-Kacheln, Fortschrittsanzeige, funktioniert auf Handy, Tablet und Kiosk-PC."),
      feature("Vertrauens-Hinweis", "Vor jeder Umfrage steht in Klartext, was mit den Antworten passiert — und was nicht."),
      feature("Teilnahme-Verlauf", "„Meine Feedbacks“ zeigt jede Runde: abgegeben, offen oder verpasst."),
      feature("Eigene Antworten ansehen", "Nach der Abgabe nur lesbar und nur auf dem eigenen Gerät gespeichert — nicht auf dem Server."),
      feature("Maßnahmen der Führungskraft", "„Was hat sich getan?“ — freigegebene Maßnahmen des eigenen Teams einsehen."),
      feature("Persönliche Sprache", "Eigene Sprache für den Fragebogen wählen, wenn dieser mehrsprachig angeboten wird."),
      feature("Anmeldung für alle", "Single Sign-on (Entra ID), Personalnummer + Einmalcode für Personen ohne E-Mail, Kiosk-Modus mit Auto-Abmeldung."),

      // ---------- Führungskräfte ----------
      roleTag("FÜR FÜHRUNGSKRÄFTE", ROLE_FK),
      h1("Den eigenen Report verstehen und nutzen"),
      lede("Alles aus der Mitarbeiter-Ansicht, zusätzlich der eigene Feedback-Report."),
      feature("Report in vier Reitern", "Überblick, Themen im Detail, Freitexte, Verlauf über mehrere Runden — klar getrennt."),
      feature("Einordnung auf einen Blick", "Vergleich mit Fachbereich, Unternehmen und Vorrunde; Ampel zeigt sofort, wo man steht."),
      feature("Weiterempfehlung (NPS)", "Würde mich mein Team weiterempfehlen? Mit Kritikern/Neutralen/Fans und Referenzwert."),
      feature("Freitexte verständlich", "Wortwolke, nach Themen gruppiert, optional KI-Zusammenfassung — immer geschwärzt."),
      feature("Export in vier Formaten", "Eigenen Report als PDF, PowerPoint, Excel oder CSV herunterladen."),
      feature("Maßnahmen ableiten", "Themenvorschläge aus dem Report übernehmen, Maßnahmen anlegen und fürs Team freigeben."),

      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Admin: Umfrage gestalten ----------
      roleTag("ADMIN", ROLE_ADMIN),
      h1("Umfrage gestalten"),
      lede("Der Fragebogen entsteht im Portal — ohne LimeSurvey-Kenntnisse."),
      feature("Themen & Reihenfolge", "Dimensionen frei anlegen, Fragen per Drag & Drop sortieren."),
      feature("Vier Fragetypen", "Likert-Skala (4–7 Stufen, jede Stufe frei beschriftbar), Weiterempfehlung (NPS), Einfach-/Mehrfachauswahl, Freitext."),
      feature("Verzweigungen", "Eine Frage nur zeigen, wenn eine frühere Frage eine Bedingung erfüllt."),
      feature("Mehrsprachig", "Beliebige Zusatzsprachen, Übersetzungsansicht mit Fortschritt, optionale KI-Übersetzung — fehlende Texte fallen auf Deutsch zurück."),
      feature("Versionierung", "Eine in Nutzung befindliche Version ist gesperrt; Änderungen laufen über „als neue Version bearbeiten“."),
      feature("Veröffentlichen", "Ein Klick überträgt den Fragebogen nach LimeSurvey — passiert sonst automatisch beim Rundenstart."),

      // ---------- Admin: Befragungsrunden ----------
      roleTag("ADMIN", ROLE_ADMIN),
      h1("Befragungsrunden"),
      lede("Vom Anlegen bis zur Erinnerung — in einem Assistenten."),
      feature("Runden-Assistent", "Drei Schritte: Fragebogen wählen, Zeitraum festlegen, bestätigen."),
      feature("Automatisch wiederkehrend", "Vierteljährlich, halbjährlich oder jährlich — die nächste Runde entsteht von selbst."),
      feature("Teams immer aktuell", "Vor jedem Rundenstart werden die Teams automatisch aus SAP aktualisiert."),
      feature("Rücklauf im Blick", "Dashboard je Fachbereich, „Erinnerung an alle Offenen“ (höchstens einmal pro Tag)."),
      feature("Ohne E-Mail-Adresse", "Code-Briefe mit QR-Code und ein Team-Aushang — ohne Teilnahmestatus einzelner Personen."),
      feature("Export", "Rücklauf je Fachbereich als CSV herunterladen."),

      // ---------- Admin: Auswertung ----------
      roleTag("ADMIN", ROLE_ADMIN),
      h1("Auswertung & Benchmarking"),
      lede("Kennzahlen für HR — nie mit Bezug auf eine einzelne Antwort."),
      feature("Statistik je Frage/Thema", "n, Minimum, Maximum, Mittelwert, Median, Standardabweichung, Verteilung."),
      feature("Frei wählbare Gruppen", "Fachbereiche miteinander vergleichen, als Balken- oder Ampel-Ansicht."),
      feature("Pseudonymer Benchmark", "Führungskräfte untereinander vergleichen — als „FK-A“, „FK-B“, nie mit echtem Namen."),
      feature("Unternehmensweiter NPS", "Mit manuell pflegbarem Referenzwert, z. B. aus einer Branchenstudie."),
      feature("Freitext-Themen", "Wortwolke und Kategorien (KI oder Schlüsselwörter) — erst ab drei Texten sichtbar."),
      feature("Export", "Als Excel, PowerPoint oder CSV, ohne unterdrückte Kleingruppen."),

      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Admin: Report-Layout ----------
      roleTag("ADMIN", ROLE_ADMIN),
      h1("Report-Layout"),
      lede("Aufbau und Wortlaut jedes Führungskraft-Reports zentral festlegen — mit Live-Vorschau."),
      feature("Abschnitte steuern", "Ein-/ausblenden und per Pfeil in beliebige Reihenfolge bringen."),
      feature("Eigene Textbausteine", "Bis zu zehn frei formulierte Abschnitte an beliebiger Stelle einfügen."),
      feature("Feste Formulierungen anpassen", "z. B. „Das läuft gut“ umbenennen — mit Rückfall auf den Standardtext."),
      feature("Platzhalter", "{leader}, {overall}, {best_topic} u. a. werden automatisch mit echten Werten befüllt."),
      feature("Farbe & Vorschau", "Akzentfarbe wählen, Änderungen sofort in der Live-Vorschau mit Beispieldaten sehen."),
      feature("Beispiel-Downloads", "Vor dem Speichern in allen vier Formaten testen."),

      // ---------- Admin: Organisation & Rechte ----------
      roleTag("ADMIN", ROLE_ADMIN),
      h1("Organisation & Rechte"),
      lede("Wer im Unternehmen wen führt — und wer im Portal was darf."),
      feature("SAP-Import", "CSV heute, SuccessFactors-Anbindung vorbereitet; Trockenlauf mit Diff-Ansicht vor der Übernahme."),
      feature("Organigramm", "Teamgrößen auf einen Blick; Teams unter drei Personen automatisch als „nicht auswertbar“ markiert."),
      feature("Personen verwalten", "Suchen, Admin-Zugang vergeben oder entziehen."),
      feature("Feine Rechte", "Eigene Zugriffsrollen anlegen — z. B. „nur Auswertung ansehen“ statt Vollzugriff."),
      feature("Audit-Log", "Jede administrative Änderung wird nachvollziehbar protokolliert."),
      feature("Automatische Löschfristen", "Rohantworten, Codes und Protokolle werden nach festen Fristen automatisch entfernt."),

      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Anonymität ----------
      eyebrow("Grundprinzip der Plattform", RULE_RED),
      h1("Anonymität & Sicherheit"),
      lede("Diese Regeln sind technisch erzwungen, nicht nur vereinbart."),
      new Table({
        width: { size: 9400, type: WidthType.DXA },
        borders: { top: { style: BorderStyle.SINGLE, size: 4, color: "D9C4BE" }, bottom: { style: BorderStyle.SINGLE, size: 4, color: "D9C4BE" }, left: { style: BorderStyle.SINGLE, size: 24, color: RULE_RED }, right: { style: BorderStyle.SINGLE, size: 4, color: "D9C4BE" }, insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE } },
        rows: [new TableRow({ children: [new TableCell({
          width: { size: 9400, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: RULE_SOFT },
          margins: { top: 260, bottom: 260, left: 320, right: 320 },
          children: [
            new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: "NICHT VERHANDELBAR", font: FONT, bold: true, size: 18, color: RULE_RED, characterSpacing: 20 })] }),
            ruleItem("Team-Schwelle:", "Eine Führungskraft wird nur bewertet, wenn ihr Team mindestens drei Personen hat."),
            ruleItem("Berichts-Schwelle:", "Ein Report oder eine Kennzahl erscheint erst ab drei abgegebenen Antworten — auf jeder Auswertungsebene."),
            ruleItem("Getrennte Systeme:", "Jede Führungskraft bekommt je Runde eine eigene Umfrage in LimeSurvey. Das Portal weiß nur „diese Person hat teilgenommen“, nie „was sie geantwortet hat“."),
            ruleItem("Geschwärzte Freitexte:", "Namen, E-Mails und Telefonnummern werden automatisch entfernt, die Reihenfolge wird gemischt."),
            ruleItem("Keine Rohantworten für Admins:", "Auch HR sieht niemals eine einzelne Antwort mit Personenbezug."),
            new Paragraph({
              bullet: { level: 0 },
              children: [
                new TextRun({ text: "Eigene Antworten: ", font: FONT, color: GREEN_DARK, size: 22, bold: true }),
                new TextRun({ text: "Nach der Abgabe nur als schreibgeschützte Kopie auf dem eigenen Gerät sichtbar — nie auf dem Server gespeichert.", font: FONT, color: GREEN_DARK, size: 22 }),
              ],
            }),
          ],
        })] })],
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Architektur ----------
      eyebrow("Technische Seite"),
      h1("Architektur im Überblick"),
      lede("Zwei Systeme mit klarer Aufgabenteilung."),
      new Paragraph({
        spacing: { after: 220 },
        children: [new TextRun({
          text: "Das Feedback-Portal ist Eigenentwicklung und steuert Organisation, Rollen, Runden und Reports. LimeSurvey bleibt unverändert der reine „Umfrage-Motor“ und bleibt dadurch update- und supportfähig.",
          font: FONT, size: 22, color: MUTED,
        })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 260 },
        children: [new ImageRun({
          type: "png",
          data: fs.readFileSync(path.join(__dirname, "architektur.png")),
          transformation: { width: 620, height: 442 },
        })],
      }),
      eyebrow("Die Bausteine im Einzelnen"),
      new Table({
        width: { size: 9400, type: WidthType.DXA },
        borders: tableBorders,
        columnWidths: [2400, 7000],
        rows: [
          new TableRow({ tableHeader: true, children: [
            cell("Baustein", { width: 2400, shading: GREEN_SOFT, bold: true, color: GREEN }),
            cell("Aufgabe", { width: 7000, shading: GREEN_SOFT, bold: true, color: GREEN }),
          ] }),
          ...[
            ["Portal-Web", "Die Oberfläche, die alle drei Rollen benutzen — im Browser, am Handy und am Kiosk-PC."],
            ["Portal-API", "Steuert Organisation, Rollen, Runden, Auswertung und Reports; einzige Verbindung zu allen anderen Systemen."],
            ["PostgreSQL", "Speichert nur, dass jemand teilgenommen hat, nie was — plus Organisation, Rollen und Reports."],
            ["LimeSurvey", "Spielt den Fragebogen aus, vergibt Einmal-Zugänge, sammelt die Antworten — unverändert im Kern."],
            ["MariaDB", "Rohantworten von LimeSurvey; werden automatisch nach 90 Tagen gelöscht."],
            ["SAP / SuccessFactors", "Liefert die Organisation — wer führt wen. Heute per CSV, Anbindung per OData vorbereitet."],
            ["Entra ID", "Single Sign-on für die Anmeldung im Portal."],
            ["Mailserver", "Versendet Einladungen und Erinnerungen — produktiv über den Firmen-Mailserver."],
            ["KI-Provider", "Optional und austauschbar — fasst Freitexte zusammen und ordnet sie Themen zu."],
          ].map(([a, b]) => new TableRow({ children: [cell(a, { width: 2400, bold: true }), cell(b, { width: 7000 })] })),
        ],
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ---------- Stand ----------
      eyebrow("Reifegrad"),
      h1("Stand & nächste Schritte"),
      lede("Ein funktionsfähiger Prototyp mit allen oben beschriebenen Funktionen, mehrfach automatisiert getestet und mit echten Testdaten durchgespielt — noch kein produktionsreifes System."),
      new Table({
        width: { size: 9400, type: WidthType.DXA },
        columnWidths: [4700, 4700],
        borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE } },
        rows: [new TableRow({ children: [
          new TableCell({
            width: { size: 4700, type: WidthType.DXA },
            margins: { right: 300 },
            borders: { top: noBorder, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
            children: [
              new Paragraph({ spacing: { before: 140, after: 120 }, children: [new TextRun({ text: "Bereits geprüft", font: FONT, bold: true, size: 23, color: "2F8F52" })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Alle Kernfunktionen automatisiert getestet", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Echte Runde mit echten Teilnahmen durchgespielt", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Anonymität direkt in der Datenbank kontrolliert", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Lasttest: 300 gleichzeitige Teilnahmen ohne Fehler", font: FONT, size: 20, color: MUTED })] }),
            ],
          }),
          new TableCell({
            width: { size: 4700, type: WidthType.DXA },
            margins: { left: 300 },
            borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
            children: [
              new Paragraph({ spacing: { before: 140, after: 120 }, children: [new TextRun({ text: "Noch zu tun", font: FONT, bold: true, size: 23, color: "A3711F" })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Freigabe durch Betriebsrat & Datenschutz", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Anbindung an echtes SAP, Entra ID und Mailserver", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "Produktionsserver mit HTTPS und Backups", font: FONT, size: 20, color: MUTED })] }),
              new Paragraph({ bullet: { level: 0 }, spacing: { after: 90 }, children: [new TextRun({ text: "KI-Provider gegen ein echtes internes Gateway testen", font: FONT, size: 20, color: MUTED })] }),
            ],
          }),
        ] })],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(__dirname, "..", "Fuehrungsfeedback-Portal-Dokumentation.docx"), buf);
  console.log("written");
});
