# Betrieb: HTTPS, Backups, Löschfristen

## HTTPS (Produktion)
1. DNS: drei Namen auf den Server (Portal, API, LimeSurvey), z. B. `feedback.firma.de`, `feedback-api.firma.de`, `umfrage.firma.de`.
2. `.env` (aus `.env.example`) ergänzen: `PORTAL_DOMAIN`, `API_DOMAIN`, `SURVEY_DOMAIN`, `APP_ENV=prod`, `PORTAL_PUBLIC_URL=https://…`, `LIMESURVEY_URL_PUBLIC=https://…`, `VITE_API_BASE_URL=https://<API_DOMAIN>` und **alle Passwörter/Secrets ändern** (`SECRET_KEY`, `FEEDBACKBRIDGE_HMAC_SECRET`, DB-, LimeSurvey-Passwörter, `APP_SSO_SECRET`).
3. Start: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
   Caddy besorgt und erneuert Zertifikate automatisch; interne Dienste sind nicht mehr direkt erreichbar. Mailpit entfällt (echter Mailversand über `SMTP_*`, siehe Outlook in `.env.example`).
4. `APP_ENV=prod` schaltet den Dev-Login ab. Erster Admin: `docker compose exec postgres psql -U portal -d portal -c "insert into role_assignment(person_id,role) select id,'admin' from person where personalnummer='<PNR>'"`, danach Rollen im Portal unter *Benutzer & Organisation*.

## Backups
`sh scripts/backup.sh` erzeugt gepackte Dumps von Portal- und LimeSurvey-Datenbank in `backups/` (14 Tage Aufbewahrung). Täglich per Cron/Aufgabenplanung ausführen und `backups/` auf ein anderes System kopieren (Backups enthalten personenbezogene Daten → verschlüsselt ablegen).
Wiederherstellung:
```bash
gunzip -c backups/portal-<STAMP>.sql.gz | docker compose exec -T postgres psql -U portal -d portal
gunzip -c backups/limesurvey-<STAMP>.sql.gz | docker compose exec -T mariadb sh -c 'mysql -u root -p"$MARIADB_ROOT_PASSWORD" limesurvey'
```
Restore einmal pro Quartal auf einer Testumgebung üben.

## Löschfristen (automatisch, täglich 03:30)
| Daten | Frist (ENV) | Standard |
|---|---|---|
| LimeSurvey-Rohantworten je Führungskraft (Umfrage wird gelöscht) | `RETENTION_SURVEY_DAYS` nach Rundenende, nur Status „berichtet“ | 90 Tage |
| In-Portal-Benachrichtigungen | `RETENTION_NOTIFICATION_DAYS` | 180 Tage |
| Login-Code-Hashes | `RETENTION_LOGIN_CODE_DAYS` | 90 Tage |
| Audit-Log | `RETENTION_AUDIT_DAYS` | 365 Tage |
| Eingelöste SSO-Assertions | fest | 1 Tag nach Ablauf |
Aggregate und geschwärzte Reports bleiben für Trendvergleiche erhalten; sie enthalten keine Einzelantworten. Fristen mit Datenschutz/Betriebsrat abstimmen (siehe `OPEN_QUESTIONS.md`).

## Monitoring (Empfehlung)
`/health` der API per Uptime-Check abfragen; Container-Logs (`docker compose logs`) zentral sammeln; Speicherplatz der Backups überwachen.
