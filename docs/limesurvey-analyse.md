# LimeSurvey-Analyse (Phase 0)

Stand: 2026-09-25. Getestet gegen `martialblog/limesurvey:6.17.18-260831-apache` (LimeSurvey Community Edition 6.17.18), MariaDB 10.11, per `docker compose up`.

## 1. RemoteControl-API (JSON-RPC)

- Endpunkt: `POST /index.php/admin/remotecontrol`, Content-Type `application/json`, Body `{"method":...,"params":[...],"id":...}`.
- **Muss explizit aktiviert werden.** Es gibt keine ENV-Variable im Docker-Image dafür. Notwendig ist ein Eintrag in der Tabelle `lime_settings_global`:
  ```sql
  INSERT INTO lime_settings_global (stg_name, stg_value) VALUES ('RPCInterface','json');
  ```
  Ohne diesen Eintrag antwortet der Endpunkt mit HTTP 200 und leerem Body (kein Fehler, einfach nichts) — das kostet beim ersten Einrichten Zeit, wenn man es nicht kennt. Wird in Phase 1 durch ein Init-Skript automatisiert (siehe `scripts/limesurvey-init.sh`, Abschnitt 6).
- Session: `get_session_key(user, pass)` → Session-Key, der bei jedem weiteren Aufruf mitgeschickt wird. `release_session_key` schließt sie.
- **Kein Verfahren zum Anlegen eingeschränkter Admin-User über die API.** `add_user` existiert in RemoteControl 2 **nicht** (offiziell bestätigt über `list_users`, das nur *liest*; ein Aufruf von `add_user` liefert `500: call_user_func_array(): ... class remotecontrol_handle does not have a method "add_user"`). Auch laut offizieller Klassendokumentation (`api.limesurvey.org/classes/remotecontrol-handle.html`) gibt es keine Methoden zum Erstellen/Verwalten von Admin-Benutzern.
  - **Konsequenz:** Der technische API-User des Portals ist der beim Container-Start über `ADMIN_USER`/`ADMIN_PASSWORD` erzeugte Superadmin-Account. Es gibt keinen eingeschränkten Zweit-Account über die API. Das ist für die Anonymitätsregeln unkritisch, **weil dieser Account nie an einen Menschen (HR/Admin) herausgegeben wird** — er lebt ausschließlich in der Server-Konfiguration des Portal-Backends. Siehe `docs/ENTSCHEIDUNGEN.md` Nr. 8. Härtung (eigener eingeschränkter Account, angelegt per Migration/DB-Skript statt UI) ist als Nice-to-have in `OPEN_QUESTIONS.md` vermerkt, kein Blocker.
- Relevante Methoden für das Portal (empirisch geprüft bzw. aus offizieller Doku bestätigt):
  - `list_surveys`, `copy_survey`, `import_survey`, `delete_survey`, `activate_survey`
  - `activate_tokens` (legt die Token-/Teilnehmertabelle für eine Umfrage an — **ohne diesen Aufruf existiert keine Tabelle**, `add_participants` schlägt sonst mit `"No survey participant list"` fehl)
  - `add_participants`, `list_participants`, `get_participant_properties`, `set_participant_properties`, `delete_participants`
  - `export_responses`, `export_responses_by_token`, `get_summary`
  - `add_group`, `import_question`, `list_questions`, `get_question_properties`, `set_question_properties`
  - `list_users` (nur lesend)

## 2. Token- und Attribut-Handling

- Teilnehmer/Tokens leben in einer pro-Umfrage-Tabelle `lime_tokens_<sid>`, angelegt durch `activate_tokens`.
- Zusätzliche Teilnehmer-Attribute (`attribute_1` … `attribute_N`) werden über die UI ("Verwalte Attribute" im Teilnehmer-Bereich) oder direkt beim Import als Spalten hinzugefügt und können bei `add_participants` mitgegeben werden. Empirisch bestätigt: `add_participants(session, sid, [{..., "attribute_1": "FK-TEST-001"}], true)` legt den Wert korrekt in der Tabelle ab.
- Der Zugriffslink für einen Teilnehmenden ist `GET /index.php/survey/index/sid/<sid>/token/<token>/lang/<lang>`.

## 3. Verhalten bei `anonymized = Y` — zentrales Ergebnis der Machbarkeitsprüfung

**Die in `CLAUDE.md` beschriebene Technik (versteckte Equation-Frage mit `{TOKEN:ATTRIBUTE_1}`) funktioniert bei `anonymized = Y` nicht — durch eine bewusste Sicherheitssperre im LimeSurvey-Kern, kein Konfigurationsfehler.**

### Was empirisch geprüft wurde
1. Testumfrage angelegt, `anonymized=Y`, `datestamp=N`, `ipaddr=N`, `tokenanswerspersistence=Y`, `printanswers=Y` (alles wie in `CLAUDE.md` gefordert).
2. `attribute_1` (`leader_code`) als Teilnehmerattribut angelegt, Testteilnehmer mit `attribute_1=FK-TEST-001` per RemoteControl erzeugt.
3. Versteckte Frage vom Typ „Gleichung" (`type: "*"`, Attribut `hidden=1`) mit `{TOKEN:ATTRIBUTE_1}` angelegt (sowohl über das Gleichungs-Attribut als auch — zur Kontrolle — direkt im Fragetext).
4. Umfrage aktiviert, Token-URL aufgerufen, Frage beantwortet, abgeschickt.
5. Ergebnis in der Antworttabelle (`lime_survey_<sid>`) geprüft: das Feld für die Gleichungsfrage war **leer**, obwohl `attribute_1` in der Teilnehmertabelle korrekt gesetzt war.
6. Zur Eingrenzung wurde `{TOKEN:ATTRIBUTE_1}` zusätzlich in den Willkommenstext gesetzt (ein Ort, an dem Token-Platzhalter laut Handbuch garantiert funktionieren) — auch dort wurde der Platzhalter zu einem **leeren String** aufgelöst.
7. Root Cause im Quellcode gefunden (`application/helpers/expressions/em_manager_helper.php`, Registrierung der `TOKEN:*`-Variablen für die Expression-Engine):
   ```php
   $this->knownVars["TOKEN:" . strtoupper((string) $key)] = [
       'code'      => $anonymized ? '' : $val,   // <-- bei anonymized=Y wird der Wert IMMER durch '' ersetzt
       ...
   ];
   ```
   LimeSurvey ersetzt bei anonymisierten Umfragen **jeden** `{TOKEN:...}`-Platzhalter durch einen Leerstring, unabhängig davon, wo er verwendet wird (Fragetext, Gleichung, Willkommenstext, E-Mail-Vorlagen). Das ist eine bewusste Schutzmaßnahme des LimeSurvey-Kerns gegen genau diese Art von Deanonymisierung und lässt sich nicht per Konfiguration umgehen.

### Entscheidung
→ **Fallback aus `TASKS.md` wird zur Zielarchitektur:** eine eigene LimeSurvey-Umfrage pro Führungskraft und Runde, statt einer gemeinsamen Umfrage mit Token-Attribut-Zuordnung. Details und Begründung in `docs/ENTSCHEIDUNGEN.md` Nr. 9. Das ist **kein Kompromiss**, sondern strukturell sauberer: die Zuordnung Antwort→Führungskraft ergibt sich aus der Survey-ID selbst (die das Portal in `round_target` verwaltet), nicht aus einem in der Antwort gespeicherten Wert. Es muss nichts aus der Antwort „herausgelesen" werden, wodurch die ursprüngliche Deanonymisierungs-Sperre von LimeSurvey gar nicht erst berührt wird.

### Was weiterhin funktioniert (bestätigt)
- `anonymized=Y` entfernt die Spalte `token` vollständig aus dem Antwort-Tabellenschema (`lime_survey_<sid>`) — keine Spalte, kein Wert, strukturell unmöglich, eine Antwort nachträglich einer Person zuzuordnen. Das Schema wird bei Aktivierung anhand von `anonymized` festgelegt und lässt sich danach nicht mehr ändern (Umschalten in der DB ohne Tabellen-Neuanlage erzeugt einen `Database error!`, empirisch bestätigt).
- Die Umfrage selbst zeigt Teilnehmenden einen expliziten Hinweistext: *"THIS SURVEY IS ANONYMOUS. […] There is no way of matching identification access codes with survey responses."* — das deckt sich mit der Zusicherung in `CLAUDE.md`.
- `datestamp=N` liefert **keinen** Zeitstempel, sondern einen fixen Dummy-Wert (`1980-01-01 00:00:00`) statt `NULL` — sogar strenger als „nur das Datum speichern". Das Portal muss das Teilnahmedatum ohnehin separat über die eigene `participation`-Tabelle führen (Webhook/Polling), nicht aus LimeSurvey auslesen.
- `printanswers=Y` funktioniert wie erwartet (Antworten sind direkt nach Abgabe druckbar).
- Das Plugin-Event `afterSurveyComplete` (siehe Abschnitt 4) erhält `surveyId` und (wenn im Session-State vorhanden) `responseId` — **nicht** `token` direkt im Event-Objekt. Der Token selbst liegt aber in `$_SESSION[...]['token']` und ist für serverseitigen PHP-Code (das Plugin läuft mit vollem DB-Zugriff, genau wie der technische API-User) ohne Weiteres lesbar — die `anonymized`-Sperre wirkt nur auf die Expression-Engine/Platzhalter-Ersetzung, nicht auf den PHP-Session-State. Das reicht für die Teilnahmestatus-Verfolgung (Portal speichert „wer hat teilgenommen", nie „was").

### Offene Anomalie (kein Blocker, dokumentiert)
Bei zwei von vier Testabgaben (jeweils die **erste** Abgabe nach frischer Aktivierung/Token-Tabellen-Anlage) wurde der Teilnahme-Token korrekt auf `completed=Y` gesetzt, **aber keine Zeile in der Antworttabelle angelegt** (`export_responses` meldete „No Data"). Nachfolgende Abgaben auf derselben Umfrage funktionierten zuverlässig. Ursache nicht abschließend geklärt (evtl. MyISAM-Tabellen-Erstverhalten oder ein Cache-Effekt direkt nach `activate_tokens`). **Mitigation:** Die in `TASKS.md` Phase 4 ohnehin vorgesehene Doppelsicherung (Webhook bei Abschluss **plus** periodisches Polling über `list_participants(completed)`) fängt diesen Fall ab, da das Polling unabhängig vom Antwort-Datensatz nur auf `completed` prüft. Für die reine Teilnahmestatus-Frage ist das ausreichend; für die Auswertung zählt ohnehin nur, wie viele tatsächliche Antwort-Datensätze vorliegen (die Schwelle ≥3 bezieht sich per Definition auf `completed_responses`, nicht auf Tokenstatus).

## 4. Plugin-Events

- Bestätigter Hook-Punkt für `FeedbackBridge`: `afterSurveyComplete` (ausgelöst in `application/helpers/SurveyRuntimeHelper.php`, unmittelbar nach Abschluss). Payload: `surveyId` immer, `responseId` wenn eine Antwort gespeichert wurde.
- Weitere für spätere Phasen relevante Standard-Events (aus dem LimeSurvey-Pluginsystem, nicht einzeln nachgetestet, aber Standard-API): `beforeSurveyActivate`, `afterSurveyActivate`, `beforeSurveySettings` (für erzwungene Pflicht-Settings beim Aktivieren, siehe unten), `newSurveySettings`.
- **Erzwingen der Pflicht-Einstellungen** (anonymized, kein Datestamp, keine IP, printanswers): am robustesten direkt beim programmatischen Erzeugen/Kopieren der Umfrage durch den Portal-Service selbst setzen (RC `set_survey_properties` bzw. direkt im Template, das kopiert wird), nicht ausschließlich über das Plugin — das Plugin dient als zusätzliche Absicherung/Korrektur, falls jemand die Einstellungen in der LimeSurvey-UI manuell ändert.

## 5. Umfragen programmatisch erzeugen — gewählter Weg

Getestet und empfohlen: **zweistufig**.

1. **Vorlage pflegen:** Eine Umfrage pro `survey_template`/`survey_version` wird einmalig über `import_survey` (Upload einer vom Portal generierten `.lss`-Datei) angelegt bzw. bei Änderungen ersetzt. Alternativ (gleichwertig, aber mehr Einzelaufrufe): `add_group` + `import_question` je Frage. `import_survey` ist robuster, weil die gesamte Struktur (Gruppen, Fragen, Bedingungen, Pflicht-Settings) in einem Schritt und atomar entsteht.
2. **Pro Runde und Führungskraft:** `copy_survey(session, template_sid, "Titel mit Runde+Leader-Code")` — **empirisch getestet und erfolgreich**: Die Kopie übernimmt Struktur *und* alle relevanten Einstellungen (`anonymized`, `datestamp`, `ipaddr` korrekt übertragen bestätigt), aber **keine** Teilnehmer-/Token-Tabelle (muss separat per `activate_tokens` + `add_participants` für genau das Team dieser Führungskraft angelegt werden) und ist zunächst inaktiv (muss separat per `activate_survey` aktiviert werden). Das ist exakt das gewünschte Verhalten für "eine Umfrage pro Führungskraft und Runde".

`copy_survey` ist damit der gewählte, robusteste Weg für die Runden-Erzeugung in Phase 4; `import_survey` für die Vorlagenpflege in Phase 3.

## 6. Automatisierung des Setups

Ein einmaliger, nicht in der Web-UI dokumentierter Schritt ist nötig, damit `docker compose up` wirklich alles bereitstellt: RemoteControl aktivieren (siehe Abschnitt 1). Wird in Phase 1 in ein Init-Skript/einen Compose-Init-Service verlagert, das nach dem ersten Start automatisch läuft (`scripts/limesurvey-init.sh`), damit die Akzeptanzkriterien aus `TASKS.md` ("LimeSurvey läuft lokal" per `docker compose up`, ohne manuelle DB-Eingriffe) tatsächlich erfüllt sind.

## 7. Theme-System (kurzer Befund, Detailarbeit in Phase 6)

- Eigene Themes liegen unter `upload/themes/survey/<themename>/` (im Docker-Image über das `upload`-Volume persistent, im `docker-compose.yml` bereits mit `./limesurvey-theme` verknüpft).
- Ein eigenes Theme wird als Kopie eines Basis-Themes (z. B. `fruity_twentythree`) angelegt und per `config.xml` registriert — kein Eingriff in den LimeSurvey-Kern nötig, passt zum Architekturgrundsatz. Detaillierte Umsetzung (Portal-Glassmorphism-Look) folgt in Phase 6.

## 8. Fazit für die Architektur

Der Architekturweg aus `CLAUDE.md` bleibt in allen Punkten außer der Token-Attribut-Zuordnung bestehen. Einzige Änderung: **eine LimeSurvey-Umfrage pro Führungskraft und Runde** statt einer gemeinsamen Umfrage mit Equation-Frage. Auswirkungen auf spätere Phasen sind in `docs/ENTSCHEIDUNGEN.md` Nr. 9 zusammengefasst.
