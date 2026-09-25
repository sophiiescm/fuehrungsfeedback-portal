#!/bin/sh
# Einmaliger Setup-Schritt fuer LimeSurvey, der ueber keine ENV-Variable des
# Docker-Images abgedeckt ist: die RemoteControl-JSON-RPC-Schnittstelle wird
# per Datenbank-Flag aktiviert (siehe docs/limesurvey-analyse.md Abschnitt 1).
# Idempotent: kann bei jedem "docker compose up" gefahrlos erneut laufen.
set -eu

: "${DB_HOST:=mariadb}"
: "${DB_NAME:=limesurvey}"
: "${DB_USER:=limesurvey}"
: "${DB_PASSWORD:?DB_PASSWORD muss gesetzt sein}"

echo "[limesurvey-init] Warte auf LimeSurvey-Datenbankschema..."
i=0
until mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" \
    -e "SELECT 1 FROM lime_settings_global LIMIT 1" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "[limesurvey-init] Zeitueberschreitung: lime_settings_global nie erschienen." >&2
    exit 1
  fi
  sleep 2
done

echo "[limesurvey-init] Aktiviere RemoteControl (JSON-RPC)..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "
  INSERT INTO lime_settings_global (stg_name, stg_value) VALUES ('RPCInterface','json')
  ON DUPLICATE KEY UPDATE stg_value='json';
"

echo "[limesurvey-init] Fertig."
