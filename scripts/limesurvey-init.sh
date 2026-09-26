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

echo "[limesurvey-init] Registriere Theme feedbackportal (mobil optimiert)..."
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "
  INSERT INTO lime_templates (name, folder, title, creation_date, author, author_email, author_url, copyright, license, version, api_version, view_folder, files_folder, description, last_update, owner_id, extends)
    SELECT 'feedbackportal','feedbackportal','Feedback-Portal',NOW(),'Fuehrungsfeedback-Portal',author_email,author_url,'MIT','MIT','1.0.0',api_version,view_folder,files_folder,'Portal-Look, mobil optimiert',NULL,owner_id,'fruity_twentythree'
    FROM lime_templates WHERE name='fruity_twentythree' AND NOT EXISTS (SELECT 1 FROM lime_templates WHERE name='feedbackportal');
  INSERT INTO lime_template_configuration (template_name, files_css, files_js, files_print_css, options, cssframework_name, cssframework_css, cssframework_js, packages_to_load)
    SELECT 'feedbackportal', '{\"add\":[\"css/portal.css\"]}', '{\"add\":[\"scripts/receipt.js\"]}', NULL, options, cssframework_name, cssframework_css, cssframework_js, packages_to_load
    FROM lime_template_configuration WHERE template_name='fruity_twentythree' AND sid IS NULL AND gsid IS NULL
    AND NOT EXISTS (SELECT 1 FROM lime_template_configuration WHERE template_name='feedbackportal') LIMIT 1;
  UPDATE lime_template_configuration SET files_js='{\"add\":[\"scripts/receipt.js\"]}' WHERE template_name='feedbackportal' AND (files_js IS NULL OR files_js NOT LIKE '%receipt.js%');
" || echo "[limesurvey-init] Theme-Registrierung uebersprungen (fruity_twentythree noch nicht vorhanden?)"

echo "[limesurvey-init] Installiere/konfiguriere Plugin FeedbackBridge..."
: "${HMAC_SECRET:=change_me_dev_hmac_secret}"
: "${PORTAL_WEBHOOK_URL:=http://portal-api:8000/feedbacks/webhook/limesurvey-complete}"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "
  INSERT INTO lime_plugins (name, plugin_type, active, priority, version)
    SELECT 'FeedbackBridge', 'upload', 1, 0, '1.0.0' FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM lime_plugins WHERE name='FeedbackBridge');
  SET @pid = (SELECT id FROM lime_plugins WHERE name='FeedbackBridge');
  DELETE FROM lime_plugin_settings WHERE plugin_id=@pid AND model IS NULL;
  INSERT INTO lime_plugin_settings (plugin_id, model, model_id, \`key\`, value) VALUES
    (@pid, NULL, NULL, 'hmac_secret', JSON_QUOTE('$HMAC_SECRET')),
    (@pid, NULL, NULL, 'portal_webhook_url', JSON_QUOTE('$PORTAL_WEBHOOK_URL'));
"

echo "[limesurvey-init] Fertig."
