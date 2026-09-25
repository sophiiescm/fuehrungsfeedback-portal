# Aufgabenliste (von oben nach unten abarbeiten)

Regeln: siehe `CLAUDE.md` → „Arbeitsmodus“. Nach jeder Phase: Tests grün, `docker compose up` läuft, Commit.

---

## Phase 0 – Grundlage und LimeSurvey verstehen
- [x] Git-Repo initialisieren. Struktur: `portal-api/`, `portal-web/`, `limesurvey-plugin/`, `limesurvey-theme/`, `docs/`, `seed/`, `docker-compose.yml`, `.env.example`
- [x] LimeSurvey 6.x (Tag pinnen) per Docker bereitstellen, MariaDB, Mailpit
- [x] LimeSurvey-Code analysieren und die Ergebnisse in `docs/limesurvey-analyse.md` festhalten:
  - RemoteControl-Methoden
  - Token- und Attribut-Handling
  - Verhalten bei `anonymized=Y`
  - Plugin-Events
  - Theme-System
  - Umfrage-Import (`.lss`)
- [x] **Machbarkeitsprüfung** (live gegen die laufende Instanz, siehe `docs/limesurvey-analyse.md` Abschnitt 3 statt eines separaten Skripts in `docs/poc/` — die Prüfung brauchte reale API-Aufrufe, Browser-Interaktion und einen Blick in den LimeSurvey-Quellcode, kein eigenständig lauffähiges Skript): anonymisierte Umfrage mit Token und `attribute_1`, versteckte Equation-Frage mit `{TOKEN:ATTRIBUTE_1}`
  - Ergebnis: Der Wert landet **nicht** in der Antwort — LimeSurvey ersetzt `{TOKEN:...}` bei `anonymized=Y` grundsätzlich durch `''` (Sicherheitssperre im Kern, Quellcode-Beleg in `docs/limesurvey-analyse.md`).
  - Ergebnis in `docs/ENTSCHEIDUNGEN.md` (Nr. 9) festgehalten. **Fallback (eine Umfrage je Führungskraft und Runde) ist jetzt Zielarchitektur**, auch in `CLAUDE.md` nachgezogen.
- [x] Prüfen, wie Umfragen programmatisch erzeugt werden (`import_survey` mit generiertem `.lss`, oder Kopie einer Vorlage + `add_group`/`import_question`). Den robustesten Weg wählen und dokumentieren.
  - Gewählt: `import_survey` (einmalig) für die Vorlagenpflege, `copy_survey` (pro Runde/Führungskraft) für die Instanzerzeugung — `copy_survey` empirisch getestet, übernimmt Struktur und Anonymitäts-Einstellungen korrekt.

**Akzeptanz:** LimeSurvey läuft lokal (`docker compose up`, RemoteControl-Aktivierung automatisiert über `limesurvey-init`), die Machbarkeitsprüfung ist dokumentiert, der Architekturweg steht fest.

## Phase 1 – Portal-Grundgerüst und Glassmorphism-Layout
- [x] FastAPI-Projekt mit Postgres, SQLAlchemy 2 und Alembic, Health-Endpunkt, Konfiguration über pydantic-settings
- [x] Datenmodell (erste Migration):
  - `person`
  - `org_unit` / `fachbereich`
  - `role_assignment`
  - `survey_template`
  - `survey_version`
  - `question`
  - `dimension`
  - `round`
  - `round_target` (bewertete FK, Pseudonym `leader_code`)
  - `participation` (person, round, target, token_ref, status, datum)
  - `result_aggregate`
  - `report`
  - `notification`
  - `mail_template`
  - `setting`
  - `import_log`
  - `audit_log`
- [x] Auth-Grundgerüst:
  - Session/JWT
  - Dev-Login
  - Rollenprüfung als Dependency
  - OIDC-Modul (Authlib, per ENV aktivierbar)
  - SAML-Stub
- [x] SvelteKit-App mit Tailwind:
  - Glassmorphism-Designsystem (Tokens, Karten, Buttons, Tabellen, Formulare)
  - Sidebar nach Rollen
  - Hell- und Dunkelmodus
  - Login-Seite (SSO-Button, Personalnummer + Code, Dev-Login)
- [x] LimeSurvey-Client im Backend (JSON-RPC-Wrapper mit Session-Handling, Retry, Tests gegen Mock)

**Akzeptanz:** Login als Admin, FK und MA möglich (per Browser gegen den vollständig containerisierten Stack verifiziert, inkl. Neustart mit frischen Volumes). Jede Rolle sieht die richtige Sidebar (Admin: 8 Menüpunkte, FK: 4, MA: 3 — exakt wie in der CLAUDE.md-Tabelle). Die Tests sind grün (13/13 Backend-Tests, `svelte-check` 0 Fehler).

## Phase 2 – Organisation, Benutzer, SAP-Import
- [x] `OrgSource`-Interface, `CsvOrgSource`, `ODataOrgSource`-Stub
- [x] Import:
  - Trockenlauf mit Diff
  - Übernahme
  - Plausibilitätsprüfungen (Zyklen, fehlende Vorgesetzte, Dubletten)
  - Protokoll
  - nächtlicher Job (konfigurierbar über `setting`-Tabelle + Admin-Endpunkt, APScheduler)
- [x] Rollen automatisch ableiten (FK = hat Unterstellte). Admin-Rolle manuell.
- [x] Benutzerverwaltung:
  - Suche und Filter (Fachbereich, Rolle, mit/ohne E-Mail)
  - Detailansicht mit Org-Pfad
  - Rollen vergeben
  - Person deaktivieren
- [x] Organigramm-Ansicht (einfacher Baum), Teams < 3 markieren
- [x] Seed-Skript mit 1.900 Personen laut `CLAUDE.md` (`seed/generate_org_csv.py`)

**Akzeptanz:** Seed-CSV wird importiert, der Diff ist korrekt, kleine Teams sind markiert, die Tests für den Import sind grün. Verifiziert: voller 1.900-Personen-Seed per `POST /organisation/import/apply` gegen den containerisierten Stack importiert (< 1s), 41 Org-Einheiten korrekt dedupliziert, 566 Teams erkannt (48 davon < 3 Personen, 8,5% — nah an der "ca. 5%"-Vorgabe), 569 Führungskraft-Rollen automatisch abgeleitet, Organigramm mit Team-zu-klein-Markierung im UI bestätigt. 34/34 Backend-Tests grün (inkl. 6 Import- und 4 Rollen-Tests), 8/8 Seed-Skript-Tests grün.

## Phase 3 – Umfrage gestalten
- [ ] Editor:
  - Abschnitte bzw. Dimensionen
  - Likert-Fragen (Skalenbreite, Polbeschriftungen, Pflicht ja/nein)
  - Freitextfragen
  - Reihenfolge per Drag & Drop
  - Vorschau
- [ ] Versionierung. Eine Version ist nach Nutzung in einer Runde gesperrt, „Als neue Version bearbeiten“ ist möglich.
- [ ] Übertragung nach LimeSurvey über den in Phase 0 gewählten Weg. Pflicht-Einstellungen setzen (anonymized, kein Datestamp, keine IP, printanswers, kein Bearbeiten nach Abschluss).
- [ ] Mitgelieferte Beispiel-Umfrage „Führungsfeedback Standard“: ca. 20 Likert-Fragen in 5 Dimensionen und 3 Freitextfragen

**Akzeptanz:** Eine Umfrage wird im Portal erstellt, in LimeSurvey angelegt und ist dort aufrufbar.

## Phase 4 – Befragungsrunden, Teilnahme, Benachrichtigungen
- [ ] Runde anlegen mit:
  - Umfrageversion
  - Start und Ende
  - Erinnerungstage
  - Report-Kanal (Portal, E-Mail, beides)
  - Zielgruppe (alle bzw. Fachbereiche)
- [ ] Beim Start:
  - Org-Snapshot erstellen
  - Ziel-FK bestimmen (Team ≥ 3)
  - Teilnahmen erzeugen: jede Person bewertet ihre direkte FK
  - Tokens in LimeSurvey anlegen (mit `attribute_1 = leader_code`)
  - Einladungen versenden
- [ ] Plugin `FeedbackBridge`: Webhook bei Abschluss (HMAC), Portal setzt `participation.status = erledigt` (nur Datum)
  - Fallback: Polling über `list_participants(completed)`
- [ ] „Meine Feedbacks“:
  - Liste offener und erledigter Feedbacks mit Fälligkeit
  - Button „Jetzt Feedback geben“ öffnet LimeSurvey mit Token
  - Hinweis zur PDF-Kopie bzw. warum spätere Einsicht nicht möglich ist
- [ ] Scheduler (APScheduler): Start, Erinnerungen (nur Offene), Schließen
- [ ] E-Mail-Vorlagen bearbeitbar, Versand über SMTP (lokal Mailpit), In-Portal-Benachrichtigungen
- [ ] Personen ohne E-Mail:
  - Code-Generierung (gehasht)
  - PDF-Serienbrief mit QR
  - Team-Aushang ohne Einzelstatus
  - Kiosk-Modus
- [ ] Admin-Dashboard: Rücklaufquote gesamt, je Fachbereich und je FK (je FK nur als „≥ Schwelle erreicht ja/nein“ plus Quote)

**Akzeptanz:** Testrunde mit Seed-Daten starten. Mails erscheinen in Mailpit. Teilnahme per Token und per Personalnummer + Code funktioniert. Eine Doppelteilnahme ist unmöglich. Erinnerungen gehen nur an Offene.

## Phase 5 – Auswertung, Reports, Benchmarking, Trend, KI
- [ ] Nach dem Schließen:
  - Antworten exportieren (`export_responses`, JSON)
  - nach `leader_code` gruppieren
  - Statistik pro Frage und Dimension (n, min, max, Mittelwert, Median, Standardabweichung, Verteilung)
  - Schwelle ≥ 3 durchsetzen
- [ ] Schwärzung der Freitexte (Namen aus Org-Daten, E-Mail, Telefon, Personalnummern) und zufällige Reihenfolge
- [ ] KI-Provider-Interface (`none` | `openai_compatible` | `anthropic`)
  - Zusammenfassung nach Themen, keine Zitate
  - Timeout und Fehler führen zu „keine Zusammenfassung“, nicht zum Abbruch
- [ ] Report für die Führungskraft:
  - Portal-Ansicht mit Charts (Balken je Dimension, Verteilung, Vergleich Fachbereich/Unternehmen, Trend)
  - PDF-Export (WeasyPrint)
  - Versand je nach Kanal
- [ ] Trend-Monitoring: Verlauf pro FK über alle Runden (Linienchart), Veränderung zur Vorrunde
- [ ] Admin-Benchmarking:
  - innerhalb eines Fachbereichs (pseudonymisiert)
  - fachbereichsübergreifend
  - Filter nach Runde
  - Unterdrückung kleiner Gruppen
- [ ] Die Sicht der Führungskraft ist nur auf eigene Reports beschränkt (Rechtetest!)

**Akzeptanz:** Aus den historischen Seed-Runden entstehen Reports. Eine FK mit 2 Antworten bekommt keinen Report, sondern einen Hinweis. Trend und Benchmark werden angezeigt. Die Statistik-Tests sind grün.

## Phase 6 – Härtung, Doku, Übergabe
- [ ] Audit-Log für Admin-Aktionen, Rate-Limiting für den Code-Login, Security-Header, CSRF
- [ ] LimeSurvey-Theme im Portal-Look
- [ ] Playwright-Smoke-Tests (3 Rollen), Locust-Lasttest (300 gleichzeitig)
- [ ] `docs/INSTALLATION.md`: Schritt für Schritt für Windows mit Docker Desktop, inkl. Seed und Test-Logins
- [ ] `docs/BEDIENUNG.md`: kurze Anleitung je Rolle
- [ ] `docs/DATENSCHUTZ-KONZEPT.md`: Entwurf der technischen und organisatorischen Maßnahmen, Anonymitätskonzept, Löschfristen – als Grundlage für Betriebsrat und Datenschutz
- [ ] `docs/ENTSCHEIDUNGEN.md` und `OPEN_QUESTIONS.md` finalisieren
- [ ] Abschlussbericht `docs/STATUS.md`: was fertig ist, was ein Stub ist, bekannte Grenzen, nächste Schritte

**Akzeptanz:** Eine neue Person kann das Projekt nach `INSTALLATION.md` starten und alle drei Rollen durchspielen.
