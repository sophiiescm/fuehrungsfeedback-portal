# Offene Fragen (von Claude Code während der Arbeit ergänzt)

Format: Frage – getroffene Annahme – Auswirkung, falls die Annahme falsch ist

- Welcher SSO-Anbieter (Entra ID, ADFS, …)? – Annahme: OIDC-kompatibel – geringe Auswirkung, da nur Konfiguration
  **Antwort (Fachseite):** Entra ID; laut Vorgesetztem auch mit Microsoft Azure möglich → OIDC gegen Entra ID (Tenant-ID/Client-ID/Secret noch zu liefern).
- Welches SAP-System liefert die Org-Daten (SuccessFactors, HCM)? – Annahme: CSV-Export – der OData-Adapter muss später implementiert werden
  **Antwort (Fachseite):** OData soll implementiert werden; System ist SAP SuccessFactors, ansonsten S/4HANA → `ODataOrgSource` gegen SuccessFactors (Entity-Namen/Zugang noch zu liefern).
- Welcher KI-Endpunkt bzw. welches Modell wird intern genutzt? – Annahme: OpenAI-kompatibles Gateway – nur Konfiguration
- Sollen Führungskräfte Freitexte roh sehen oder nur die KI-Zusammenfassung? – Annahme: beides, roh nur geschwärzt und ab ≥ 3 Antworten
  **Antwort (Fachseite):** Ja, beides sehen. Freitexte sollen zusätzlich **kategorisiert** werden und auf keinen Fall rückverfolgbar sein.
- Soll der technische LimeSurvey-API-User über einen eingeschränkten Zweit-Account (statt des Superadmin-Accounts) laufen? – Annahme: Superadmin-Account reicht, da er nie an Menschen ausgegeben wird (siehe `docs/ENTSCHEIDUNGEN.md` Nr. 8) – Auswirkung, falls falsch: zusätzliche Härtung nötig (Account per DB-Migration mit eingeschränkten `lime_permissions`-Einträgen anlegen, da RemoteControl dafür keine Methode bietet); rein defensive Maßnahme, kein funktionaler Blocker.
- Warum verliert LimeSurvey vereinzelt die allererste Antwort direkt nach `activate_tokens` (Token wird `completed=Y`, aber keine Zeile in der Antworttabelle, siehe `docs/limesurvey-analyse.md` Abschnitt 3)? – Annahme: seltener Rand-Effekt der MyISAM-Tabellen-Erstanlage, abgefangen durch die ohnehin geplante Doppelsicherung (Webhook + Polling) in Phase 4 – Auswirkung, falls die Ursache tiefer liegt: ggf. zusätzliche Retry-Logik beim Rundenstart nötig (z. B. ein "Kanarienvogel"-Testdurchlauf pro neu aktivierter Umfrage).
- Wie lange dürfen Einzelantworten und Teilnahmestatus aufbewahrt werden (Betriebsrat/DSB)? – Annahme: Vorschlag in `docs/DATENSCHUTZ-KONZEPT.md` (Einzelantworten ≤ 3 Monate nach Rundenschluss) – ein automatischer Löschjob fehlt noch und ist nach Freigabe der Fristen zu bauen.
- Ist der Schwellenwert 3 (Einladung und Bericht) für Betriebsrat/DSB ausreichend oder soll er höher liegen? – Annahme: 3, konfigurierbar (`MIN_RESPONSES_FOR_REPORT`, nie < 3) – bei höherem Wert sinkt die Zahl auswertbarer Teams.
- Muss der Report als PDF-Anhang per E-Mail zugestellt werden oder reicht Portal-Abruf plus Benachrichtigungsmail? – Annahme: Portal-Abruf – ein Anhang wäre ein kleiner Zusatz in `app/services/evaluation.py`, hat aber Datenschutzfolgen (Report liegt dann im Postfach).
- Welches interne Ziel (Hosting, TLS, SMTP-Relay, Backup) gilt für den Betrieb? – Annahme: nur lokale Entwicklung mit Docker – vor Produktivbetrieb Reverse-Proxy/TLS, Secrets-Verwaltung und Backups ergänzen.

## Weitere Fachseiten-Vorgaben (Notizen aus Demo-Review, `Feedback_Plattform_Notizen.docx`)
- **Anmeldung ohne E-Mail:** Auch Personen ohne E-Mail sollen ein SSO-artiges Verfahren bekommen: Das Portal wird als Service in der Mitarbeiter-App bereitgestellt; dort sind die Personen bereits angemeldet und als Firmenangehörige bekannt. → Umsetzung als „Trusted-App-SSO“: die Mitarbeiter-App übergibt eine kurzlebige, signierte Assertion (Personalnummer, Ablauf, Einmal-ID) an das Portal. Code-Brief bleibt als Fallback. (Annahme: die App kann serverseitig ein gemeinsames Geheimnis halten bzw. ein OIDC-Token von Entra ID weiterreichen.)
- **Empfängerdaten bei Einladungen aus SAP:** Annahme: Name/E-Mail/Personalnummer kommen aus dem SAP-Import (SuccessFactors) und werden im Admin-Bereich als Empfängervorschau angezeigt.
- **Mailpit:** Annahme: nur Testphase; produktiv Outlook/Exchange Online (Microsoft 365) per SMTP-Relay bzw. Microsoft Graph. Zugangsdaten/Absenderadresse noch zu liefern.
- **NPS / externes Benchmarking:** Annahme: NPS-Frage (0–10) wird in die Beispielumfrage aufgenommen; „extern“ = manuell hinterlegbarer Referenzwert (Branchen-/Vergleichs-NPS), da keine externe Datenquelle bekannt ist.
- **Wordcloud:** Annahme: nur aus geschwärzten Freitexten, Wörter nur, wenn sie in ≥ 3 verschiedenen Antworten vorkommen (Rückverfolgbarkeit).
- **Automatisierung der Runden:** Annahme: wiederkehrende Runden (Standard halbjährlich) aus einer Vorlage automatisch anlegen und starten.

## Umsetzungsstand Schritt 4 – offene Punkte für die Fachseite / IT
1. **Mitarbeiter-App-SSO:** Kann die Mitarbeiter-App eine signierte Assertion (HS256, Geheimnis wird gemeinsam vereinbart, Format siehe ENTSCHEIDUNGEN Nr. 33) erzeugen? Alternative wäre ein OIDC-Login der App als IdP. *Annahme:* Assertion-Variante; Geheimnis über `APP_SSO_SECRET`.
2. **Entra ID:** Tenant-ID, Client-ID/-Secret, Redirect-URI (`…/auth/callback`) und welcher Claim die Person identifiziert (E-Mail/UPN oder Personalnummer). *Annahme:* `email` = Portal-E-Mail.
3. **SuccessFactors OData:** Endpoint, technischer User, tatsächliche Feldnamen (Zuordnung ist per `field_map` anpassbar) und Statuswerte für „aktiv". *Annahme:* Standard-Entität `User`.
4. **Outlook-Versand:** Exchange Online SMTP-AUTH ist oft deaktiviert; Alternative wäre Microsoft Graph (`sendMail`) mit App-Registrierung. *Annahme:* SMTP mit Dienstkonto oder internes Relay.
5. **KI für Kategorien:** Ohne konfigurierten Provider wird ein Schlüsselwort-Verfahren genutzt (gröber). Freigabe eines Providers durch Datenschutz nötig, da (geschwärzte) Freitexte verarbeitet werden.

## Neu: Mobile Bedienung, Maßnahmen, Betrieb – Annahmen und Rückfragen
1. **Mitarbeiter-Sicht:** Annahme: „ca. 5 Minuten“ als fester Text (Fragebogen mit 26 Fragen). Soll die Dauer aus der Fragenzahl berechnet werden? Sollen Texte zweisprachig (z. B. EN/TR/PL) angeboten werden? (Aufwand: Übersetzungen für Portal + LimeSurvey-Sprachen.)
2. **Maßnahmen:** Annahme: Führungskräfte dürfen Maßnahmen für ihr Team veröffentlichen; keine Freigabe durch HR. Abstimmung mit Betriebsrat/HR nötig, ob Maßnahmen für Vorgesetzte oder HR einsehbar sein sollen (aktuell nein).
3. **Löschfristen:** Annahme 90 Tage für LimeSurvey-Rohantworten nach Rundenende, 180 Tage Benachrichtigungen, 365 Tage Audit-Log. Bitte Datenschutz/Betriebsrat prüfen (`docs/BETRIEB.md`).
4. **HTTPS/Hosting:** Welche Domains und welche Infrastruktur (eigener Server, Azure, Kubernetes)? Annahme: ein Docker-Host mit Caddy. Zertifikate ggf. über die Firmen-CA statt Let's Encrypt.
5. **PWA/Push:** Home-Bildschirm-Icon ist vorhanden. Echte Push-Erinnerungen setzen die Mitarbeiter-App-Anbindung (Push-API der App) voraus – offen.
6. **Testgeräte:** Mobile Darstellung wurde in der Browser-Emulation (375×812) geprüft; ein Test auf echten iPhones/iPads und Kiosk-Geräten steht aus.

## Neu: Rechte, Skalen, Mindestteamgröße
1. **Rechte-Katalog:** Reichen die fünf Rechte (Umfragen, Runden, Auswertung ansehen, Benutzer/Organisation, Einstellungen)? Gewünscht evtl. feiner, z. B. Auswertung nur für den eigenen Fachbereich einschränken (Datenscope) oder Exporte separat berechtigen. *Annahme:* aktueller Katalog; Rollen frei kombinierbar.
2. **Auswertungs-Admins und Betriebsrat/Datenschutz:** Dürfen Auswertungs-Admins alle Führungskräfte pseudonymisiert vergleichen (FK-A, FK-B …)? *Annahme:* ja, wie bisher; Namen der Führungskräfte sehen sie im Rücklauf (Runden-Dashboard) – ggf. ebenfalls pseudonymisieren?
3. **Team < 3 während laufender Runde:** Wenn SAP zwischenzeitlich ein Team unter 3 Personen bringt, gilt der Start-Snapshot. Soll die Runde für dieses Team abgebrochen werden? *Annahme:* nein (Snapshot).
4. **Skalenbeschriftungen:** Standardtexte („Trifft gar nicht zu … Trifft voll zu“) sind Vorschläge – bitte fachlich prüfen/anpassen. Mehrsprachigkeit der Beschriftungen offen.
5. **Zugriffsrollen im Betrieb:** Sollen Rollen künftig aus Entra-ID-Gruppen kommen statt im Portal gepflegt zu werden? *Annahme:* Pflege im Portal.

## Neu: Report-Layout und Exporte
1. **Firmen-Design:** Für PowerPoint/PDF gibt es Akzentfarbe, Titel und Fußzeile. Sollen Logo, Firmenschrift oder eine PowerPoint-Master-Vorlage der Firma verwendet werden? (Dafür bitte die .potx-Vorlage und das Logo bereitstellen.) *Annahme:* schlichtes Standarddesign.
2. **Freitexte in Excel/CSV:** Standard: aus. Sollen Führungskräfte die geschwärzten Freitexte exportieren dürfen? Datenschutz/Betriebsrat klären, da Dateien das Portal verlassen.
3. **Weitergabe:** Exportierte Reports sind nicht mit einem Wasserzeichen versehen. Soll „Vertraulich – nur für [Name]“ als Wasserzeichen/Fußzeile pro Person eingesetzt werden? (Platzhalter {leader} ist bereits in Titel/Untertitel möglich.)
4. **Report-Layout je Runde oder Fachbereich:** Aktuell ein globales Layout. Sind unterschiedliche Layouts (z. B. für Produktion vs. Büro) gewünscht?
5. **Sprache:** Reports sind deutsch; Mehrsprachigkeit offen.

## Neu: Eigene Antworten ansehen und SAP-Teams
1. **Antwort-Kopie nur lokal:** Damit die Anonymität erhalten bleibt, liegt die Kopie nur im Browser des Geräts, auf dem abgegeben wurde (nicht auf dem Server, nicht auf Kiosk-Geräten). Wer das Gerät wechselt oder Browserdaten löscht, sieht sie nicht mehr. Reicht das? Eine serverseitige (auch verschlüsselte) Speicherung würde die Person↔Antwort-Verknüpfung schaffen und braucht die ausdrückliche Freigabe von Betriebsrat/Datenschutz und eine Änderung der Regel in CLAUDE.md.
2. **Mitarbeiter-App:** Wenn Mitarbeitende die Umfrage künftig in der Mitarbeiter-App öffnen (Webview), gilt „Gerät“ = App-Speicher; bitte prüfen, ob der Webview localStorage dauerhaft behält.
3. **SAP-Quelle für Auto-Aktualisierung:** Damit Teams vor jeder Runde automatisch aktualisiert werden, muss unter Organisation → Import-Zeitplan die Quelle (OData oder CSV) aktiviert und `ODATA_*` gesetzt sein (Zugangsdaten offen, siehe oben). Ohne Quelle gilt der zuletzt manuell importierte Stand.

## Neu: Mehrsprachigkeit und Runden-Assistent
1. **Sprachen:** Welche Sprachen werden gebraucht (Katalog enthält 20, u. a. EN, TR, PL, RU, RO, UK, AR)? Wer übersetzt bzw. prüft die Texte (Fachabteilung, Übersetzungsbüro)? *Annahme:* manuelle Pflege im Editor, KI-Vorschlag nur optional und immer zu prüfen. Arabisch (rechts-nach-links) ist im Umfrage-Theme nicht gesondert getestet.
2. **Sprache als Rückschluss:** LimeSurvey speichert die Startsprache jeder Antwort. In Teams mit nur einer Person einer Sprache ließe sich eine Antwort erraten. Soll die Sprachwahl trotzdem erlaubt sein (Annahme: ja, Rohdaten sind nicht zugänglich und werden nach 90 Tagen gelöscht) oder nur, wenn ≥ 3 Personen der Sprache im Team sind?
3. **Übrige Texte:** E-Mail-Einladungen, Portal-Oberfläche, PDF/PowerPoint-Reports sind deutsch. Soll das Portal selbst auch mehrsprachig werden (Aufwand: Übersetzung aller Oberflächentexte)?
4. **KI-Übersetzung:** Freigabe eines Providers durch Datenschutz nötig (Fragetexte sind unkritisch, enthalten aber keine personenbezogenen Daten).
