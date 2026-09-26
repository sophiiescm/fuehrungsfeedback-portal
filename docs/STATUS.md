# Status (Stand 2026-09-26)

Alle Phasen 0–6 aus `TASKS.md` sind umgesetzt und committet (ein Commit je Phase). Alle Daten sind fiktiv (Seed-Skripte).
**Es ist ein funktionsfähiger Prototyp, kein produktionsreifes Produkt** (siehe „Bekannte Grenzen“).

## Architektur-Kernentscheidung (Abweichung von `CLAUDE.md`, dort nachgezogen)
Die geplante Zuordnung „Antwort → Führungskraft“ über eine versteckte Equation-Frage mit `{TOKEN:ATTRIBUTE_1}` **funktioniert nicht**:
LimeSurvey ersetzt bei `anonymized=Y` jeden `{TOKEN:…}`-Platzhalter bewusst durch einen Leerstring (Quellcode-Beleg in
`docs/limesurvey-analyse.md`). Zielarchitektur ist daher der in `TASKS.md` vorgesehene Fallback: **eine LimeSurvey-Umfrage pro
Führungskraft und Runde** (per `copy_survey` aus der Vorlage). Das ist ohnehin sauberer. Alle Entscheidungen: `docs/ENTSCHEIDUNGEN.md` (Nr. 1–24).

## Was fertig ist (und wie es geprüft wurde)
| Bereich | Stand | Nachweis |
|---|---|---|
| Stack per `docker compose up` | postgres, mariadb, limesurvey (6.17.18 gepinnt), mailpit, portal-api, portal-web; RemoteControl und Plugin werden automatisch eingerichtet | Neustart mit gelöschten Volumes durchgespielt (Installationsanleitung Schritt für Schritt) |
| Login / Rollen | Dev-Login, Code-Login (Personalnummer + Einmalcode, gehasht, Rate-Limit), Rollenprüfung, Sidebar je Rolle, Hell/Dunkel, responsiv | Tests, Playwright (5 Tests, 3 Rollen + Mobil), Browser |
| SAP-Import | CSV, Trockenlauf mit Diff, Plausibilitätsprüfung (Zyklen/fehlende Vorgesetzte/Dubletten), Protokoll, nächtlicher Job, automatische Rollen, Organigramm mit Teams < 3 markiert | 1.900-Personen-Import < 1 s, Tests |
| Umfrage-Editor | Dimensionen, Likert (4–7 Stufen, Pole), Freitext, Drag & Drop, Vorschau, Versionierung/Sperre, Übertragung nach LimeSurvey | Tests, Browser, echte LimeSurvey-Umfrage |
| Runden | Anlegen/Starten/Schließen, Snapshot, eine Umfrage je auswertbarer FK (Team ≥ 3), Tokens, Einladungen (Mail + Portal), Erinnerungen nur an Offene, Scheduler (15 Min.), Polling-Fallback, Rücklauf-Dashboard | Echte Runde: 66 FK, 235 Teilnahmen, 147 Mails in Mailpit |
| Teilnahme | „Meine Feedbacks“, Token-Link, Hinweis zur PDF-Kopie, FeedbackBridge-Webhook (HMAC) | Echte Abgabe → Webhook setzte `erledigt` (ohne Polling) |
| Ohne E-Mail | Code-Briefe mit QR (PDF), Team-Aushang ohne Einzelstatus, Kiosk-Auto-Logout (3 Min.) | Tests, PDF im Container gerendert |
| Auswertung | Statistik je Frage/Dimension, Schwelle ≥ 3 (hart), Schwärzung + Mischen, KI-Interface, Report (Portal + PDF), Trend, Vergleich Fachbereich/Unternehmen/Vorrunde, pseudonymisierter Benchmark | Echte Auswertung von 3 echten Antworten; 2 Historien-Runden (518 FK) |
| Sicherheit | Audit-Log (Admin-Schreibzugriffe), Rate-Limit, Security-Header, Rechtetest über alle Endpunkte, Secrets nur per ENV | Tests |
| Anonymität (real geprüft) | LimeSurvey-Antworttabelle hat **keine** Spalten `token`, `ipaddr`, `datestamp`, `startdate`, `refurl`; Zeitstempel = Dummy 1980-01-01 | direkt in MariaDB kontrolliert |
| Last | 300 gleichzeitige Teilnahmen, 1.644 Requests, **0 Fehler** (Öffnen p50 2,5 s / p95 12 s, Seiten-POST p95 3 s auf einem einzelnen Dev-Container) | Locust |
| Tests | 75 Backend-Tests (im Container inkl. PDF), 8 Seed-Tests, 5 Playwright-Tests, `svelte-check` 0 Fehler | |

## Nur Stub / vorbereitet
- **SSO (OIDC):** Konfiguration und Authlib-Client sind vorhanden, der Redirect-/Callback-Flow ist **nicht** verdrahtet (kein IdP zum Testen; `/auth/oidc/login` liefert 501). **SAML:** nur Stub (`app/auth/saml_stub.py`).
- **`ODataOrgSource`** (SuccessFactors/SAP HCM): Stub, wirft `NotImplementedError`. Aktiv ist der CSV-Import.
- **KI-Zusammenfassung:** Provider `openai_compatible` und `anthropic` sind implementiert, aber **nicht gegen einen echten Endpunkt getestet**; Standard ist `none`.
- **LimeSurvey-Theme** `limesurvey-theme/` ist angelegt (erbt `fruity_twentythree`), muss einmal in LimeSurvey installiert werden und wird noch nicht automatisch auf die Umfragen angewendet; visuell nicht geprüft.
- **Report-Versand per E-Mail:** Kanal „E-Mail“/„beides“ verschickt die Benachrichtigungs-Mail, aber **ohne PDF-Anhang** (PDF im Portal abrufbar).

## Bekannte Grenzen / Risiken
- **Kein Löschjob** für Einzelantworten/Teilnahmestatus (Fristen: `docs/DATENSCHUTZ-KONZEPT.md`); Umfragen in LimeSurvey müssen bis dahin manuell gelöscht werden.
- **Rate-Limit** ist pro API-Prozess (In-Memory); bei mehreren Instanzen gemeinsamen Speicher (z. B. Redis) nachrüsten.
- **Technischer LimeSurvey-Account** ist der Superadmin (RemoteControl kann keine eingeschränkten Nutzer anlegen, `OPEN_QUESTIONS.md`); nie an Personen herausgeben.
- **LimeSurvey 6 hat den Support-Status „Extended Support“;** 7.x existiert. Migration einplanen.
- **Rundenstart** ist synchron (~0,7 s je Führungskraft, ~50 s für 66 FK); bei mehreren hundert FK als Hintergrund-Job umbauen.
- **Bekannte LimeSurvey-Anomalie** (Phase 0): sehr selten geht die erste Antwort direkt nach Aktivierung verloren; Polling-Abgleich fängt den Teilnahmestatus ab, die Antwort selbst nicht. Vor Produktivstart mit „Kanarienvogel-Teilnahme“ je Runde absichern.
- Personen mit E-Mail aus dem Seed heißen `…@example.test`; für echten Mailversand SMTP konfigurieren (`SMTP_*`).
- Ein SAP-Import ist ein Vollabzug: fehlende Personen werden deaktiviert (auch die `DEV-*`-Startkonten).
- Kein TLS/Reverse-Proxy im Compose-Setup; Backups nicht enthalten.
- Nicht live geprüft: Plugin-Aktivierung über die LimeSurvey-Oberfläche (die automatische Installation über die Datenbank ist geprüft), Drag & Drop im Editor nur über die API/Tests, nicht per Maus-Automation.
- UI-Feinschliff: Screenshot-Tool war teilweise nicht nutzbar; Seiten wurden über Textinhalt/Netzwerk/Playwright geprüft, nicht flächendeckend visuell.

## Nächste Schritte
1. Betriebsrat/Datenschutz (`docs/DATENSCHUTZ-KONZEPT.md`, offene Punkte dort) und Antworten auf `OPEN_QUESTIONS.md`.
2. OIDC-Flow mit echtem IdP fertigstellen; SAP-Anbindung (OData/SFTP) statt manueller CSV.
3. Löschjob, Backups, TLS/Reverse-Proxy, gemeinsamer Rate-Limit-Speicher, Rundenstart als Hintergrund-Job.
4. KI-Provider gegen internes Gateway testen (nach Freigabe).
5. Theme installieren/prüfen; LimeSurvey-Upgrade auf 7.x planen.

## Starten
Siehe `docs/INSTALLATION.md`. Kurzfassung:
```powershell
copy .env.example .env
docker compose up -d --build
# Portal http://localhost:5173  |  Mailpit http://localhost:8025  |  LimeSurvey http://localhost:8080
```
Test-Logins und Seed-Reihenfolge: `docs/INSTALLATION.md` Abschnitt 2–3. Bedienung: `docs/BEDIENUNG.md`.

## Nachtrag: Umsetzung der Fachseiten-Wünsche (nach Demo)
Fertig und getestet (93 Backend-Tests, `npm run check` sauber):
- **Reports/Auswertung:** überarbeitete Report-Seite (PDF-Button oben rechts), Wortwolke, Themen-Kategorien, NPS, Vergleichsgruppen frei wählbar, Balken-/Ampel-Ansicht, NPS-Referenzwert manuell pflegbar, PDF enthält NPS/Auswahl/Themen.
- **Umfrage-Editor:** Likert, NPS, Einfach-/Mehrfachauswahl, mehrere Freitextfelder, Hilfetexte, Verzweigungen.
- **Runden-Automatisierung:** wiederkehrende Runden (z. B. halbjährlich) im Admin-UI „Befragungsrunden"; Empfänger-Vorschau.
- **Anmeldung:** Trusted-App-SSO (`/sso#assertion=…`), Entra-ID-OIDC-Flow (`/auth/callback`), Code-Brief als Fallback.
- **Anbindungen:** `ODataOrgSource` (SuccessFactors) nutzbar im nächtlichen Import, Outlook/Exchange-SMTP (STARTTLS+Login).
Nur gegen Mocks getestet (echte Systeme fehlen): Entra ID, SuccessFactors, Exchange Online, KI-Kategorisierung – siehe `OPEN_QUESTIONS.md`.
Bekannt: `tests/test_rounds.py::test_leader_code_is_not_derived_from_personalnummer` ist selten flaky (Zufallscode). Demo-Daten wurden nicht neu gesät; für NPS/Auswahl-Demo `docker compose down -v` und Seed neu ausführen.

## Nachtrag 2: Mobile Bedienung, Mitarbeiter-Sicht, Maßnahmen, Betrieb
Fertig und getestet (97 Backend-Tests, 8 Playwright-Tests inkl. iPhone-/iPad-Viewport mit Screenshots in `portal-web/e2e/screens/`):
- **Mobil/Tablet:** Tab-Leiste unten (< 1024 px), Sidebar darauf ab Desktop, iOS-Safe-Areas, PWA-Manifest; LimeSurvey-Theme `feedbackportal` mit großen Antwort-Kacheln und Fortschrittsanzeige.
- **Mitarbeiter:** Vertrauens-Hinweis, klare Karten mit Frist, rollenbasiertes Dashboard.
- **Maßnahmen** („Was hat sich getan?“): Führungskräfte legen Maßnahmen an, Team sieht die freigegebenen.
- **Admin:** Runden-Assistent (4 Schritte), Veröffentlichen automatisch beim Start, „Erinnerung an alle Offenen“, Rücklauf-Balken, CSV-Exporte, Admin-Rolle im Portal vergeben.
- **Betrieb:** `docker-compose.prod.yml` (HTTPS/Caddy), `scripts/backup.sh`, automatische Löschfristen – siehe `docs/BETRIEB.md`.
Nicht getestet: echte iPhones/iPads/Kiosk-Geräte, Produktions-HTTPS mit echten Domains, Lasttest nach Theme-Änderung (Format „Gruppe für Gruppe“ unverändert). Offene Rückfragen: `OPEN_QUESTIONS.md` (Abschnitt „Neu: Mobile Bedienung …“).

## Nachtrag 3: Rechte, Skalen, Dev-Ansichten
- Nutzer & Rechte (Einstellungen): eigene Zugriffsrollen mit fünf Rechten, Admins mit unterschiedlichen Befugnissen (z. B. „Nur Auswertung“), serverseitig erzwungen, 8 neue Tests.
- Umfrage-Editor: jede Likert-Stufe einzeln beschriftbar (4–7 Stufen), Auswahlfragen mit einzelnen Optionsfeldern, Mehrfachantworten als Checkboxen.
- Mindestteamgröße auch in „Meine Feedbacks“ erzwungen; Erklärtext dort entfernt.
- Dev: Schnellzugriff auf alle Ansichten, „Ansicht wechseln“. Angemeldete Person rechts oben (Benutzermenü). Mitarbeiter-App-Simulator wieder entfernt.
- Tests: 105 Backend, 12 Playwright. Neue Rückfragen: `OPEN_QUESTIONS.md` („Neu: Rechte, Skalen, Mindestteamgröße“).

## Nachtrag 4: Report-Layout und Exporte
- Admin-Oberfläche „Report-Layout“ mit Live-Vorschau und Beispiel-Downloads; Export der Reports als PDF, PowerPoint, Excel, CSV (Führungskraft: eigener Report; Auswertungs-Admin: Benchmark).
- Tests: 111 Backend (inkl. 6 neue), 13 Playwright. PDF/PowerPoint/Excel/CSV im Docker-Container geprüft (HTTP 200, gültige Dateien); Öffnen in echtem PowerPoint/Excel nicht geprüft.
- Neue Rückfragen: `OPEN_QUESTIONS.md` („Neu: Report-Layout und Exporte“).

## Nachtrag 5: Teilnahme-Verlauf, lokale Antwortkopie, SAP-Teams automatisch
- „Meine Feedbacks“: Verlauf mit Status je Runde; abgegebene Antworten nur lesbar und – anonymitätsgerecht – als lokale Kopie auf dem Gerät ansehbar (Ende-zu-Ende in echtem Browser mit LimeSurvey geprüft: 26 Antworten wurden übernommen).
- Teams werden vor jedem Rundenstart aus der SAP-Quelle aktualisiert; Assistent zeigt Stand und „Jetzt aus SAP aktualisieren“ (Mock/CSV getestet, echtes SAP nicht).
- Tests: 113 Backend, 14 Playwright.
