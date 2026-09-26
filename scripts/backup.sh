#!/bin/sh
# Sicherung von Portal-DB (Postgres) und LimeSurvey-DB (MariaDB) nach ./backups, Aufbewahrung 14 Tage.
# Aufruf (z. B. taeglich per Cron):  sh scripts/backup.sh
# Wiederherstellung: siehe docs/BETRIEB.md
set -eu
cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-portal}" "${POSTGRES_DB:-portal}" | gzip > "backups/portal-$STAMP.sql.gz"
docker compose exec -T mariadb sh -c 'mysqldump -u root -p"$MARIADB_ROOT_PASSWORD" --single-transaction limesurvey' | gzip > "backups/limesurvey-$STAMP.sql.gz"
find backups -name '*.sql.gz' -mtime +14 -delete
echo "Backup fertig: backups/portal-$STAMP.sql.gz, backups/limesurvey-$STAMP.sql.gz"
