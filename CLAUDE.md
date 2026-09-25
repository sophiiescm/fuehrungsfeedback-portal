# Projekt: Führungskräfte-Feedback auf Basis von LimeSurvey

## Arbeitsmodus (WICHTIG)
- Arbeite `TASKS.md` von oben nach unten **eigenständig** ab. Hake erledigte Aufgaben ab (`- [x]`).
- Nach jeder Phase: Tests ausführen, Anwendung starten, Akzeptanzkriterien prüfen, dann committen (`git commit -m "Phase N: ..."`).
- **Nicht nachfragen**, wenn eine sinnvolle Standardentscheidung möglich ist. Stattdessen entscheiden und die Entscheidung in `docs/ENTSCHEIDUNGEN.md` mit Begründung festhalten.
- Echte Blocker oder Fragen, die nur die Fachseite beantworten kann, in `OPEN_QUESTIONS.md` sammeln und **mit einer Annahme weiterarbeiten**.
- Wenn ein Ansatz nach 3 Versuchen scheitert: Fallback laut `TASKS.md` nehmen, dokumentieren, weitermachen.
- Sprache: UI, Doku und Kommentare auf **Deutsch**. Code-Bezeichner auf Englisch.

## Ziel
Webplattform für ein **Upward-Feedback**: Mitarbeitende bewerten halbjährlich anonym ihre direkte Führungskraft. Führungskräfte bewerten wiederum ihre eigene Führungskraft. Ergebnisse werden anonymisiert und aggregiert als Report an die Führungskraft geliefert. HR/Personalentwicklung verwaltet alles und sieht Benchmarks und Trends.
Größenordnung: ca. 1.900 Teilnehmende, wachsend.

## Architekturgrundsatz
**LimeSurvey wird NICHT im Kern verändert.** Es bleibt updatefähig und supportfähig.
LimeSurvey ist der „Motor“ (Fragebogen ausspielen, Token, Einmal-Teilnahme). Alles andere liegt im eigenen Portal.

```
┌──────────────────────── Feedback-Portal ────────────────────────┐
│ Frontend: SvelteKit + TypeScript + Tailwind (Glassmorphism)     │
│ Backend:  FastAPI + SQLAlchemy 2 + Alembic + APScheduler        │
│ DB:       PostgreSQL (Portal-Daten: Org, Rollen, Runden, Reports)│
└───────┬───────────────────────┬──────────────────────┬──────────┘
        │ RemoteControl JSON-RPC │ Webhook (Plugin)     │ Adapter
        ▼                        │                      ▼
┌──────────────── LimeSurvey 6.x ┘        SAP (CSV → später OData)
│ + Plugin "FeedbackBridge"                SSO (OIDC, optional SAML)
│ DB: MariaDB                              KI (austauschbarer Provider)
└──────────────────────────────            Mail (SMTP; lokal Mailpit)
```

Alles läuft per `docker compose up` (Dienste: portal-api, portal-web, postgres, limesurvey, mariadb, mailpit).

## Fachliche Regeln
### Organisation und Rollen
- Jede Person hat genau eine direkte Führungskraft (`manager_personalnummer`), Quelle ist SAP.
- **Team einer Führungskraft** = ihre direkten Unterstellten.
- **Rollen:**
  - `admin` (HR/Personalentwicklung): wird manuell vergeben.
  - `fuehrungskraft`: wird automatisch vergeben, wenn die Person ≥ 1 direkt Unterstellte hat.
  - `mitarbeiter`: alle Personen.
- Eine Person kann mehrere Rollen haben. Die Sichtbarkeit in der UI richtet sich nach den Rollen.

### Anonymität (nicht verhandelbar)
1. **Einladungsschwelle:** Eine Führungskraft wird nur bewertet, wenn ihr Team **≥ 3 Personen** hat. Sonst wird sie ausgeschlossen und im Admin-Bereich als „nicht auswertbar“ markiert.
2. **Berichtsschwelle:** Ein Report bzw. eine Kennzahl wird nur angezeigt, wenn **≥ 3 abgeschlossene Antworten** vorliegen. Die Schwelle ist in den Einstellungen konfigurierbar, aber niemals < 3. Das gilt für jede Aggregationsebene (auch Benchmarks: Gruppen mit < 3 Führungskräften bzw. < 3 Antworten werden unterdrückt).
3. **Trennung von Person und Antwort:**
   - Die LimeSurvey-Umfrage läuft mit `anonymized = Y`, Datestamp aus und IP-Speicherung aus.
   - Das Portal speichert nur *dass* jemand teilgenommen hat (Status pro Runde), nie *was*.
   - Keinen exakten Abschlusszeitpunkt speichern, nur das Datum.
4. **Zuordnung Antwort → Führungskraft:**
   - **Aktualisiert in Phase 0 (siehe `docs/limesurvey-analyse.md` Abschnitt 3 und `docs/ENTSCHEIDUNGEN.md` Nr. 9):** Die ursprünglich vorgesehene Technik (Token-Attribut `attribute_1 = leader_code` + versteckte Equation-Frage mit `{TOKEN:ATTRIBUTE_1}`) funktioniert bei `anonymized=Y` nicht — LimeSurvey ersetzt `{TOKEN:...}`-Platzhalter in anonymisierten Umfragen grundsätzlich durch einen Leerstring (bewusste Sicherheitssperre im Kern, kein Konfigurationsfehler).
   - **Zielarchitektur (Fallback aus `TASKS.md`, jetzt verbindlich):** Für jede Runde und jede auswertbare Führungskraft (Team ≥ 3) wird eine **eigene** LimeSurvey-Umfrage angelegt (per `copy_survey` aus der gepflegten Vorlage). Die Zuordnung Antwort → Führungskraft ergibt sich aus der Survey-ID, die das Portal in `round_target` verwaltet — nicht aus einem in der Antwort gespeicherten Wert.
   - Die Antwort enthält damit weiterhin nichts, was Rückschlüsse auf *von wem* oder *über wen* (über die Survey-Zuordnung im Portal hinaus) zulässt.
5. **Freitext:**
   - Vor jeder Anzeige oder KI-Verarbeitung werden Namen aus den Org-Daten, E-Mail-Adressen, Telefonnummern und Personalnummern automatisch geschwärzt.
   - Rohtexte werden in zufälliger Reihenfolge angezeigt.
6. **Eigene Antworten einsehen:**
   - Nur direkt nach der Abgabe über die LimeSurvey-Funktion „Antworten drucken/als PDF speichern“ (`printanswers = Y`).
   - Später ist das bewusst nicht möglich, weil keine Verknüpfung gespeichert wird. Das soll in der UI erklärt werden.
7. **Einmal-Teilnahme:** Pro Person, Runde und Führungskraft genau ein Token. Nach Abgabe kann nichts mehr geändert werden (Speichern und Weitermachen erlaubt, Bearbeiten nach Abschluss nicht).
8. Admins sehen **keine** Rohantworten mit Personenbezug. Auch in LimeSurvey selbst haben Portal-Admins nur einen technischen API-User.

### Befragungsrunde (Lebenszyklus)
`entwurf → geplant → offen → geschlossen → ausgewertet → berichtet`

- **Admin legt fest:**
  - den Fragebogen
  - Start und Ende
  - die Erinnerungstage (Standard: 7 und 2 Tage vor Ende)
  - den Report-Versand (Portal, E-Mail oder beides)
- **Scheduler:**
  - Beim Start: Teilnehmende aus dem aktuellen Org-Stand erzeugen (Snapshot!) und einladen.
  - Erinnerungen nur an Personen, die noch nicht teilgenommen haben.
  - Beim Ende: schließen, auswerten, Reports erzeugen und verteilen.
- **Rhythmus:** halbjährlich (Voreinstellung). Trends werden **pro Befragungsrunde** verglichen.

### Umfragen
- Nur Likert-Fragen (Standard 5-stufig, konfigurierbar 4–7, mit Beschriftung der Pole) und Freitextfragen.
- Likert-Fragen sind **Dimensionen** zugeordnet (z. B. Kommunikation, Wertschätzung, Entwicklung). Die Dimensionen werden mit ausgewertet.
- Umfragen werden im Portal gestaltet und versioniert (eine Runde friert eine Version ein).

### Auswertung
- **Pro Frage und Dimension:**
  - n
  - Minimum
  - Maximum
  - Mittelwert
  - Median
  - Standardabweichung
  - Häufigkeitsverteilung
- **Vergleichswerte:**
  - Fachbereich
  - Gesamtunternehmen
  - Vorrunde (Trend)
- **Benchmarking (Admin):**
  - innerhalb eines Fachbereichs (Führungskräfte untereinander, pseudonymisiert als FK-A, FK-B …)
  - fachbereichsübergreifend
- **Trend-Monitoring:** Verlauf einer Führungskraft über alle Runden.
- **KI-Zusammenfassung** der geschwärzten Freitexte:
  - Provider austauschbar: `none` (Standard), `openai_compatible` (Base-URL + Key + Modellname, deckt interne Gateways ab), `anthropic`.
  - Konfiguration über ENV bzw. die Admin-Einstellungen.
  - Prompt so formulieren, dass Themen zusammengefasst werden, ohne wörtliche Zitate und ohne Rückschlüsse auf Personen.

### Anmeldung
- **SSO** über OIDC (z. B. Entra ID) per Authlib, konfigurierbar über ENV. SAML als vorbereitetes Modul oder Stub.
- **Produktionsmitarbeitende ohne E-Mail:**
  - Anmeldung mit Personalnummer + Einmalcode.
  - Der Code wird pro Runde erzeugt, im System nur gehasht gespeichert und als druckbarer Brief mit QR-Code bereitgestellt (PDF-Serienbrief für HR).
  - Optionaler Kiosk-Modus: automatischer Logout nach Abgabe bzw. nach 3 Minuten Inaktivität.
- **Lokale Entwicklung:** Dev-Login (Auswahl eines Testnutzers), nur aktiv wenn `APP_ENV=dev`.

### Benachrichtigungen
- **E-Mail über SMTP:** Einladung, Erinnerung, Fälligkeitshinweis, Report verfügbar bzw. Report als PDF-Anhang. Die Vorlagen sind im Portal bearbeitbar.
- **In-Portal-Benachrichtigungen** für alle. Für Personen ohne E-Mail zusätzlich:
  - eine druckbare Liste bzw. einen Aushang pro Team (ohne Teilnahmestatus einzelner Personen!)
  - die Code-Briefe
- Mitarbeitende sehen auf ihrer Startseite nur: **„Du hast X offene Feedbacks“** bzw. „Alles erledigt“, mit Fälligkeitsdatum.

## UI (Glassmorphism)
- **Layout:** feste Sidebar links, Inhalt rechts. Halbtransparente Karten (`backdrop-filter: blur`), weicher Farbverlauf im Hintergrund.
- **Barrierefreiheit:** Kontrast nach WCAG AA trotz Glas-Effekt (Text immer auf ausreichend opakem Untergrund). Hell- und Dunkelmodus.
- **Sidebar je nach Rolle:**

| Bereich | Admin | Führungskraft | Mitarbeiter |
|---|---|---|---|
| Dashboard | Gesamtstatus, Rücklaufquoten | eigener Report-Überblick | offene Aufgaben |
| Meine Feedbacks | ✓ | ✓ | ✓ |
| Meine Reports / Trend | – | ✓ | – |
| Umfrage gestalten | ✓ | – | – |
| Befragungsrunden | ✓ | – | – |
| Benutzerverwaltung & Organisation | ✓ | – | – |
| Auswertung & Benchmarking | ✓ | – | – |
| Benachrichtigungen | ✓ (Vorlagen + Versand) | ✓ (Posteingang) | ✓ (Posteingang) |
| Einstellungen | ✓ | – | – |

- Responsiv. Die Teilnahme muss auf dem Smartphone und an Kiosk-PCs gut funktionieren.

## SAP-Schnittstelle
- Adapter-Interface `OrgSource` mit Implementierung `CsvOrgSource` (jetzt) und `ODataOrgSource` (Stub für SuccessFactors bzw. SAP HCM).
- **CSV-Format** (UTF-8, Semikolon): `personalnummer;vorname;nachname;email;org_einheit;fachbereich;manager_personalnummer;standort;aktiv`
- **Import:**
  - Trockenlauf mit Diff-Anzeige (neu, geändert, deaktiviert), danach Übernahme.
  - Das Protokoll wird gespeichert.
  - Plausibilitätsprüfungen: Zyklen, fehlende Vorgesetzte, doppelte Personalnummern.
- Nächtlicher Import ist per Scheduler konfigurierbar.

## LimeSurvey
- Version: aktuelles stabiles 6.x aus `https://github.com/LimeSurvey/LimeSurvey` (Tag pinnen).
- Kommunikation ausschließlich über die RemoteControl-API (JSON-RPC) mit einem technischen User.
- **Plugin `FeedbackBridge`** (in `limesurvey-plugin/`):
  - bei `afterSurveyComplete` ein Webhook an das Portal (Token + Survey-ID, HMAC-signiert), damit das Portal den Teilnahmestatus setzt. Da seit Phase 0 eine Umfrage genau einer Führungskraft+Runde entspricht (siehe „Zuordnung Antwort → Führungskraft" oben), identifiziert die Survey-ID die Führungskraft, der Token die teilnehmende Person — beides nur für die Status-Verfolgung, nie für die Zuordnung zur Antwort selbst.
  - erzwingt die Pflicht-Einstellungen der Feedback-Umfragen (anonymized, kein Datestamp, keine IP, printanswers)
- Einheitliches Erscheinungsbild: ein LimeSurvey-Theme im Portal-Look (eigenes Theme, kein Kern-Eingriff).

## Qualität
- **Backend:** pytest. Pflicht-Tests für Anonymitätsschwellen, Statistik, Schwärzung, Org-Import und Rechteprüfung pro Endpunkt.
- **Frontend:** Playwright-Smoke-Tests für die drei Rollen.
- **Seed-Skript:** 1.900 fiktive Personen, 8 Fachbereiche, 5–6 Hierarchieebenen, ca. 5 % Teams mit < 3 Personen, ca. 30 % ohne E-Mail, 2 abgeschlossene historische Runden mit simulierten Antworten (für Trend und Benchmark).
- Lasttest (einfach, z. B. Locust): 300 gleichzeitige Teilnahmen ohne Fehler.
- Keine Secrets im Repo. `.env.example` pflegen.
