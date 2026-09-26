# Bedienung – kurze Anleitung je Rolle

## Mitarbeitende
- **Anmeldung:** per SSO (Button „Mit Single Sign-On anmelden“) oder – ohne E-Mail-Adresse – mit
  Personalnummer und dem Einmalcode aus dem Brief (Code oder QR-Code auf dem Brief).
  Am Kiosk-PC meldet das Portal nach 3 Minuten Inaktivität automatisch ab.
- **Dashboard / Meine Feedbacks:** zeigt „Du hast X offene Feedbacks“ mit Fälligkeitsdatum oder „Alles erledigt“.
  *Jetzt Feedback geben* öffnet die Umfrage. Zwischenspeichern („später fortfahren“) ist möglich, nach dem Absenden nicht mehr bearbeitbar.
- **Anonymität:** Das Portal speichert nur, *dass* du teilgenommen hast, nie *was* du geantwortet hast.
  Deshalb kannst du deine Antworten später nicht mehr einsehen. Direkt nach dem Absenden kannst du sie
  über „Antworten drucken / als PDF speichern“ sichern.
- **Benachrichtigungen:** Posteingang für Einladungen, Erinnerungen, Report-Hinweise.

## Führungskräfte
Alles wie Mitarbeitende, zusätzlich:
- **Meine Reports / Trend:** Report je Runde: Mittelwert, Median, Standardabweichung, Min/Max und Verteilung je Dimension
  und Frage; Vergleich mit Fachbereich, Gesamtunternehmen und Vorrunde; Freitexte (geschwärzt, zufällige Reihenfolge)
  und – falls aktiviert – eine KI-Zusammenfassung; PDF-Download; Trend-Diagramm über alle Runden.
- **Kein Report?** Liegen weniger als 3 abgeschlossene Antworten vor (oder hat das Team weniger als 3 Personen),
  erscheint stattdessen ein Hinweis. Das schützt die Anonymität und ist so gewollt.
- Du siehst ausschließlich eigene Reports.

## Admin (HR / Personalentwicklung)
- **Benutzerverwaltung & Organisation:** Personen suchen/filtern (Fachbereich, Rolle, mit/ohne E-Mail),
  Organigramm (Teams unter der Schwelle sind rot markiert), SAP-CSV-Import mit Trockenlauf und Diff-Vorschau,
  Plausibilitätshinweise (Zyklen, fehlende Vorgesetzte, Dubletten). Admin-Rolle wird manuell vergeben
  (`POST /organisation/persons/{id}/admin-role`), Führungskraft-/Mitarbeiter-Rolle automatisch.
- **Umfrage gestalten:** Vorlage anlegen, Dimensionen und Fragen (Likert 4–7 Stufen mit Pol-Beschriftung; Freitext) anlegen,
  per Drag & Drop sortieren, Vorschau, *An LimeSurvey übertragen*. Eine in einer Runde verwendete Version ist gesperrt →
  *Als neue Version bearbeiten*.
- **Befragungsrunden:** Runde anlegen (Version, Start/Ende, Erinnerungstage, Zielgruppe), starten, schließen;
  *Rücklauf* zeigt Quote gesamt, je Fachbereich und je Führungskraft (nur „Schwelle erreicht ja/nein“ + Quote, nie Einzelpersonen);
  *Code-Briefe (PDF)* für Personen ohne E-Mail, *Team-Aushang (PDF)* ohne Teilnahmestatus.
- **Auswertung & Benchmarking:** geschlossene Runde *auswerten*, *Reports verteilen*; Benchmark je Fachbereich und
  fachbereichsübergreifend, Führungskräfte pseudonymisiert (FK-A, FK-B …), Gruppen unter 3 Führungskräften werden unterdrückt.
- **Benachrichtigungen:** E-Mail-Vorlagen bearbeiten (Platzhalter: `{{ round_name }}`, `{{ end_date }}`, `{{ feedback_link }}`, `{{ days_left }}`).
- Admins sehen **keine** Rohantworten mit Personenbezug; alle schreibenden Admin-Aktionen landen im Audit-Log (`audit_log`).
