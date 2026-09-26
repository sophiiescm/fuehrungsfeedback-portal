# Installation (Windows mit Docker Desktop)

Alle Daten im Projekt sind fiktiv. Getestet mit Docker Desktop (Compose v2) unter Windows 11.

## Voraussetzungen
- Docker Desktop (läuft, WSL2-Backend)
- Git; optional Python 3.12+ und Node 22+ (nur für Seed-Skripte, lokale Tests und Playwright)
- Freie Ports: 5173 (Portal), 8001 (API), 8080 (LimeSurvey), 8025/1025 (Mailpit), 5432 (Postgres).
  Belegt einer davon, in `.env` `PORTAL_API_PORT`, `PORTAL_WEB_PORT` anpassen (und `VITE_API_BASE_URL`).

## 1. Starten
```powershell
git clone <repo> fuehrungsfeedback-portal
cd fuehrungsfeedback-portal
copy .env.example .env
docker compose up -d --build
```
Das startet: `postgres`, `mariadb`, `limesurvey` (gepinnt 6.17.18), `limesurvey-init` (aktiviert die
RemoteControl-API automatisch), `portal-api` (führt Alembic-Migrationen aus), `portal-web`, `mailpit`.
Warten, bis `docker compose ps` alle Dienste als *healthy/Up* zeigt (ca. 1–2 Minuten).

| Dienst | URL |
|---|---|
| Portal | http://localhost:5173 |
| API-Doku | http://localhost:8001/docs |
| LimeSurvey-Admin | http://localhost:8080/index.php/admin (admin / `admin_dev_password`) |
| Mailpit (alle Mails) | http://localhost:8025 |

## 2. Testdaten einspielen (Seed)
Die Seed-Skripte laufen im `portal-api`-venv. Einmalig:
```powershell
cd portal-api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # falls nicht vorhanden: DATABASE_URL=postgresql+psycopg://portal:portal_dev_password@localhost:5432/portal
cd ..
```
Dann der Reihe nach (aus dem Ordner `portal-api`):
```powershell
# 1) 1.900 fiktive Personen erzeugen und importieren
python ..\seed\generate_org_csv.py                 # schreibt seed\output\org.csv
```
`org.csv` im Portal importieren: Login (Schritt 3) → *Benutzerverwaltung & Organisation* → *SAP-Import* →
Datei wählen → *Trockenlauf* → *Übernehmen*.
> **Wichtig:** Ein SAP-Import ist ein vollständiger Snapshot – wer nicht in der Datei steht, wird deaktiviert.
> Die drei `DEV-*`-Startkonten werden dadurch deaktiviert. Vor dem ersten Import daher mit `DEV-ADMIN` anmelden;
> danach eine echte Person zum Admin machen (siehe Schritt 3) oder `P00001` per SQL:
> `docker compose exec postgres psql -U portal -d portal -c "insert into role_assignment(person_id,role) select id,'admin' from person where personalnummer='P00001'"`

```powershell
# 2) Beispiel-Umfrage "Führungsfeedback Standard" (20 Likert + 3 Freitext, 5 Dimensionen)
.venv\Scripts\python ..\seed\seed_survey_template.py
# 3) zwei historische Runden mit simulierten Antworten (für Trend/Benchmark)
.venv\Scripts\python ..\seed\seed_history.py
```
Danach im Portal: *Umfrage gestalten* → Vorlage öffnen → **An LimeSurvey übertragen** (nötig, bevor eine Runde starten kann).

## 3. Test-Logins
Im Entwicklungsmodus (`APP_ENV=dev`) zeigt die Login-Seite eine Dev-Login-Liste (die ersten 50 aktiven Personen).

| Rolle | Personalnummer (Seed 42) |
|---|---|
| Admin (+ Führungskraft) | `P00001` (Admin-Rolle siehe Hinweis oben) bzw. vor dem Import `DEV-ADMIN` |
| Führungskraft | `P00002` (mit historischen Reports) |
| Mitarbeiter | `P00783` (nach Start einer Runde mit offenen Feedbacks) |
| Ohne E-Mail (Code-Login) | Personalnummer + Code aus dem Code-Brief (*Befragungsrunden → Code-Briefe (PDF)*) |

## 4. Erste Runde durchspielen
1. *Befragungsrunden* → Name, Umfrageversion, Start/Ende, ggf. Zielgruppe → *Runde anlegen* → *Jetzt starten*
   (pro auswertbarer Führungskraft wird eine LimeSurvey-Kopie angelegt; dauert ~0,7 s je Führungskraft).
2. Einladungen erscheinen in Mailpit (Personen mit E-Mail) bzw. als Code-Brief-PDF (ohne E-Mail).
3. Als Mitarbeiter: *Meine Feedbacks* → *Jetzt Feedback geben* → Umfrage ausfüllen.
4. Der Teilnahmestatus wird per Webhook (Plugin) oder spätestens durch den 15-Minuten-Abgleich gesetzt.
5. *Schließen* → *Auswertung & Benchmarking* → *Auswerten* → *Reports verteilen*.

## 5. FeedbackBridge-Plugin und Theme in LimeSurvey
- **Plugin:** wird von `limesurvey-init` beim Start automatisch installiert, aktiviert und mit Webhook-URL sowie
  `FEEDBACKBRIDGE_HMAC_SECRET` aus `.env` konfiguriert (kein Klick nötig). Prüfen: LimeSurvey → *Konfiguration → Plugins*.
- **Theme (optional):** *Konfiguration → Themes → Dateien scannen* → **feedbackportal** installieren (Look wie im Portal).
  Wird derzeit nicht automatisch auf die Umfragen angewendet (siehe `docs/STATUS.md`).
Ohne Plugin funktioniert das System weiter: der Polling-Abgleich (alle 15 Min.) setzt den Teilnahmestatus.

## 6. Tests
```powershell
cd portal-api;  .venv\Scripts\python -m pytest                 # Backend (PDF-Test läuft nur im Container)
docker compose exec portal-api python -m pytest -q             # inkl. PDF-Rendering
cd ..\seed;     python -m pytest                               # Seed-Invarianten
cd ..\portal-web; npm install; npm run check; npm run test:e2e # Playwright gegen den laufenden Stack
pip install locust; locust -f loadtest/locustfile.py --headless -u 300 -r 50 -t 150s -H http://localhost:8080
```
Lasttest-Vorbereitung siehe Kopf von `loadtest/locustfile.py` (Token-Export).

## 7. Zurücksetzen
```powershell
docker compose down -v    # löscht ALLE Daten (Postgres, MariaDB, LimeSurvey-Uploads)
```

## Konfiguration (`.env`)
Siehe `.env.example`. Wichtig für den Produktivbetrieb: `APP_ENV=prod` (schaltet Dev-Login ab), neue Werte für
`SECRET_KEY`, `FEEDBACKBRIDGE_HMAC_SECRET`, alle Passwörter; `OIDC_*` für SSO; `SMTP_*` für den Mailserver;
`AI_PROVIDER` (`none` | `openai_compatible` | `anthropic`) samt `AI_BASE_URL/AI_API_KEY/AI_MODEL`.
