# Offene Fragen (von Claude Code während der Arbeit ergänzt)

Format: Frage – getroffene Annahme – Auswirkung, falls die Annahme falsch ist

- Welcher SSO-Anbieter (Entra ID, ADFS, …)? – Annahme: OIDC-kompatibel – geringe Auswirkung, da nur Konfiguration
- Welches SAP-System liefert die Org-Daten (SuccessFactors, HCM)? – Annahme: CSV-Export – der OData-Adapter muss später implementiert werden
- Welcher KI-Endpunkt bzw. welches Modell wird intern genutzt? – Annahme: OpenAI-kompatibles Gateway – nur Konfiguration
- Sollen Führungskräfte Freitexte roh sehen oder nur die KI-Zusammenfassung? – Annahme: beides, roh nur geschwärzt und ab ≥ 3 Antworten
- Soll der technische LimeSurvey-API-User über einen eingeschränkten Zweit-Account (statt des Superadmin-Accounts) laufen? – Annahme: Superadmin-Account reicht, da er nie an Menschen ausgegeben wird (siehe `docs/ENTSCHEIDUNGEN.md` Nr. 8) – Auswirkung, falls falsch: zusätzliche Härtung nötig (Account per DB-Migration mit eingeschränkten `lime_permissions`-Einträgen anlegen, da RemoteControl dafür keine Methode bietet); rein defensive Maßnahme, kein funktionaler Blocker.
- Warum verliert LimeSurvey vereinzelt die allererste Antwort direkt nach `activate_tokens` (Token wird `completed=Y`, aber keine Zeile in der Antworttabelle, siehe `docs/limesurvey-analyse.md` Abschnitt 3)? – Annahme: seltener Rand-Effekt der MyISAM-Tabellen-Erstanlage, abgefangen durch die ohnehin geplante Doppelsicherung (Webhook + Polling) in Phase 4 – Auswirkung, falls die Ursache tiefer liegt: ggf. zusätzliche Retry-Logik beim Rundenstart nötig (z. B. ein "Kanarienvogel"-Testdurchlauf pro neu aktivierter Umfrage).
- Wie lange dürfen Einzelantworten und Teilnahmestatus aufbewahrt werden (Betriebsrat/DSB)? – Annahme: Vorschlag in `docs/DATENSCHUTZ-KONZEPT.md` (Einzelantworten ≤ 3 Monate nach Rundenschluss) – ein automatischer Löschjob fehlt noch und ist nach Freigabe der Fristen zu bauen.
- Ist der Schwellenwert 3 (Einladung und Bericht) für Betriebsrat/DSB ausreichend oder soll er höher liegen? – Annahme: 3, konfigurierbar (`MIN_RESPONSES_FOR_REPORT`, nie < 3) – bei höherem Wert sinkt die Zahl auswertbarer Teams.
- Muss der Report als PDF-Anhang per E-Mail zugestellt werden oder reicht Portal-Abruf plus Benachrichtigungsmail? – Annahme: Portal-Abruf – ein Anhang wäre ein kleiner Zusatz in `app/services/evaluation.py`, hat aber Datenschutzfolgen (Report liegt dann im Postfach).
- Welches interne Ziel (Hosting, TLS, SMTP-Relay, Backup) gilt für den Betrieb? – Annahme: nur lokale Entwicklung mit Docker – vor Produktivbetrieb Reverse-Proxy/TLS, Secrets-Verwaltung und Backups ergänzen.
