# Datenschutzkonzept (Entwurf)

Grundlage für die Abstimmung mit Betriebsrat und Datenschutzbeauftragten. **Entwurf, keine Rechtsberatung** –
Rechtsgrundlage, Betriebsvereinbarung und Verzeichnis der Verarbeitungstätigkeiten sind noch zu klären.

## 1. Zweck und Verarbeitung
Halbjährliches Upward-Feedback: Mitarbeitende bewerten anonym ihre direkte Führungskraft; Führungskräfte erhalten
aggregierte Reports; HR sieht Rücklauf, Benchmarks und Trends. Ca. 1.900 Personen.

| Datenkategorie | Inhalt | Speicherort | Zweck |
|---|---|---|---|
| Stammdaten (aus SAP) | Personalnummer, Name, E-Mail, Org-Einheit, Fachbereich, Vorgesetzte(r), Standort | Portal-DB (Postgres) | Rollen, Einladungen, Team-Zuordnung |
| Teilnahmestatus | Person × Runde × Führungskraft: offen/erledigt, **nur Datum** | Portal-DB | Erinnerungen, Rücklaufquote |
| Umfrageantworten | Likert-Werte, Freitext – **ohne Personenbezug** | LimeSurvey-DB (MariaDB), Antworttabelle je Führungskraft und Runde | Auswertung |
| Aggregate | n, Min, Max, Mittelwert, Median, σ, Verteilung je Frage/Dimension | Portal-DB | Reports, Trends, Benchmarks |
| Freitexte | geschwärzt, zufällig gemischt, nur bei ≥ 3 Texten | Portal-DB | Report |
| Login-Codes | nur bcrypt-Hash | Portal-DB | Anmeldung ohne E-Mail |
| Audit-Log | Admin, Aktion, Zeitpunkt (keine Inhalte) | Portal-DB | Nachvollziehbarkeit |

## 2. Anonymitätskonzept (technisch erzwungen)
1. **Einladungsschwelle:** Führungskräfte mit weniger als 3 Unterstellten werden nicht bewertet (keine Umfrage, keine Einladung), im Admin-Bereich nur als „nicht auswertbar“ geführt.
2. **Berichtsschwelle:** Kennzahlen/Reports nur ab ≥ 3 abgeschlossenen Antworten (konfigurierbar, nie < 3; im Code hart begrenzt). Gilt auch für Vergleichswerte und Benchmarks (Gruppen < 3 Führungskräfte werden unterdrückt) sowie für Freitexte (< 3 Texte → nicht angezeigt).
3. **Trennung Person ↔ Antwort:** Jede Führungskraft und Runde hat eine **eigene** LimeSurvey-Umfrage mit `anonymized=Y`,
   ohne Datestamp, ohne IP, ohne Referrer/Timings. LimeSurvey legt in der Antworttabelle bei `anonymized=Y` **gar keine Token-Spalte** an;
   ein späteres Umschalten ist nicht möglich. Die Zuordnung Antwort → Führungskraft ergibt sich allein aus der Umfrage-ID
   (Portal-Tabelle `round_target`), nicht aus einem Antwortfeld (siehe `docs/ENTSCHEIDUNGEN.md` Nr. 9 und `docs/limesurvey-analyse.md`).
   Das Portal speichert Teilnahme (Token ↔ Person) und nie Antworten; LimeSurvey speichert Antworten und nie die Person.
   Der Abschluss-Zeitstempel der Antwort ist ein Dummy-Wert (1980-01-01), das Portal speichert nur das Datum der Teilnahme.
4. **Freitext:** vor Anzeige/KI-Verarbeitung automatische Schwärzung (Namen aus den Org-Daten, E-Mail, Telefon, Personalnummern), zufällige Reihenfolge.
5. **Eigene Antworten:** einsehbar nur direkt nach Abgabe (LimeSurvey „Antworten drucken“), später bewusst nicht.
6. **Einmal-Teilnahme:** ein Token je Person, Runde und Führungskraft; nach Abschluss nicht änderbar.
7. **Admins** erhalten keine Rohantworten; Zugriff auf LimeSurvey nur über einen technischen Service-Account (nicht an Personen ausgegeben).
   Reports sind ausschließlich für die bewertete Führungskraft abrufbar (auch Admins nicht).
8. **Restrisiken:** Bei kleinen Teams (3–4 Personen) können Freitext-Formulierungen Rückschlüsse erlauben (Schwärzung ersetzt keine
   Sensibilisierung). Wer selbst im Team ist, kennt seine eigene Antwort. Ein Datenbankadministrator mit direktem Zugriff auf beide Datenbanken
   sieht Teilnahme (Postgres) und Antworten (MariaDB) getrennt; eine Verknüpfung ist strukturell nicht möglich (keine Token-Spalte).

## 3. Technische und organisatorische Maßnahmen (TOM)
- Rollen/Rechteprüfung pro Endpunkt (automatisierter Test über alle Routen), JWT-Anmeldung, SSO (OIDC) für Beschäftigte mit E-Mail.
- Anmeldung ohne E-Mail: Einmalcode (gehasht), Rate-Limit (5 Fehlversuche/15 Min.), optionaler Kiosk-Modus (Auto-Logout nach 3 Min.).
- Webhook LimeSurvey → Portal HMAC-signiert (nur Umfrage-ID + Token).
- Security-Header (nosniff, Frame-Verbot, CSP, HSTS außerhalb von dev). CSRF: API nutzt Bearer-Tokens im Header (keine Cookies) → klassisches CSRF nicht anwendbar.
- Audit-Log aller schreibenden Admin-Aktionen.
- Secrets nur per Umgebungsvariablen, keine Zugangsdaten im Repository.
- Transportverschlüsselung (TLS) und Netzsegmentierung sind Aufgabe der Betriebsumgebung (Reverse-Proxy) – im Docker-Setup der Entwicklung nicht enthalten.
- KI-Zusammenfassung standardmäßig **aus**; nur geschwärzte Texte, Prompt verbietet Zitate und Rückschlüsse; Provider austauschbar (auch interne Gateways).
  **Vor Aktivierung Freigabe durch Betriebsrat/Datenschutz einholen.**

## 4. Löschfristen (Vorschlag, abzustimmen)
| Daten | Vorschlag |
|---|---|
| Einzelantworten in LimeSurvey | nach Auswertung und Verteilung der Reports, spätestens 3 Monate nach Rundenschluss (Umfrage löschen) |
| Teilnahmestatus, Login-Codes | 12 Monate nach Rundenschluss |
| Aggregate, Reports | 3 Jahre (Trendvergleich) |
| Freitexte (geschwärzt) | wie Reports |
| Stammdaten | Deaktivierung bei Ausscheiden (SAP-Sync); Löschung/Pseudonymisierung nach Fristen des Personalwesens |
| Audit-Log | 12 Monate |
Ein automatischer Löschjob ist **implementiert** (täglich 03:30; Rohantworten 90 Tage, Benachrichtigungen 180, Login-Codes 90, Audit 365 Tage, per ENV änderbar, siehe `docs/BETRIEB.md`). Teilnahmestatus, Aggregate/Reports und Stammdaten werden noch nicht automatisch gelöscht (nach Abstimmung mit dem Betriebsrat ergänzen).

## 5. Offene Punkte für Betriebsrat/DSB
Rechtsgrundlage und Betriebsvereinbarung; Schwellenwert (≥ 3 vs. höher); Freigabe KI; Löschfristen; Auftragsverarbeitung (Hosting, ggf. KI-Anbieter);
Datenschutz-Folgenabschätzung; Umgang mit Teams unter der Schwelle; Rechte Betroffener (Auskunft betrifft nur Stammdaten/Teilnahmestatus).
