<?php

if (!defined('BASEPATH')) {
    die('No direct script access allowed');
}

/**
 * FeedbackBridge: verbindet LimeSurvey mit dem Fuehrungsfeedback-Portal,
 * OHNE den LimeSurvey-Kern zu veraendern (CLAUDE.md Architekturgrundsatz).
 *
 * Aufgaben:
 * 1. Bei afterSurveyComplete: sendet einen HMAC-signierten Webhook an das
 *    Portal (nur Token + Survey-ID -- niemals Antwortinhalte), damit das
 *    Portal den Teilnahmestatus setzen kann.
 * 2. Erzwingt bei jeder Feedback-Umfrage die Pflicht-Einstellungen
 *    (anonymized, kein Datestamp, keine IP, printanswers,
 *    tokenanswerspersistence), falls jemand sie in der LimeSurvey-UI manuell
 *    aendert. Das Portal setzt diese Werte bereits beim Uebertragen/Kopieren
 *    (siehe app/services/survey_export.py), diese Pruefung ist die
 *    zusaetzliche Absicherung.
 *
 * Installation: Ordnerinhalt nach upload/plugins/FeedbackBridge/ kopieren
 * (im docker-compose.yml bereits als Volume eingebunden), dann in der
 * LimeSurvey-Administration unter "Plugins" aktivieren und die Einstellungen
 * (Portal-Webhook-URL, HMAC-Secret) setzen.
 */
class FeedbackBridge extends PluginBase
{
    protected $storage = 'DbStorage';

    static protected $description = 'Verbindet LimeSurvey mit dem Fuehrungsfeedback-Portal (Teilnahmestatus, Pflicht-Einstellungen).';
    static protected $name = 'FeedbackBridge';

    protected $settings = [
        'portal_webhook_url' => [
            'type' => 'string',
            'label' => 'Portal-Webhook-URL',
            'default' => 'http://portal-api:8000/feedbacks/webhook/limesurvey-complete',
        ],
        'hmac_secret' => [
            'type' => 'string',
            'label' => 'HMAC-Secret (muss mit FEEDBACKBRIDGE_HMAC_SECRET im Portal uebereinstimmen)',
            'default' => '',
        ],
    ];

    public function init()
    {
        $this->subscribe('afterSurveyComplete');
        $this->subscribe('beforeSurveyActivate');
    }

    /**
     * Sendet bei Abschluss einer Umfrage einen signierten Webhook ans Portal.
     * Liest absichtlich nur Survey-ID und Token aus der Session -- niemals
     * die abgegebenen Antworten (CLAUDE.md Anonymitaetsregeln).
     */
    public function afterSurveyComplete()
    {
        $event = $this->getEvent();
        $surveyId = (int) $event->get('surveyId');

        $sessionKey = 'survey_' . $surveyId;
        $token = isset($_SESSION[$sessionKey]['token']) ? $_SESSION[$sessionKey]['token'] : null;
        if (!$token) {
            // Keine Token-basierte Teilnahme (z.B. Vorschau) -- nichts zu melden.
            return;
        }

        $secret = $this->get('hmac_secret', null, null, '');
        $webhookUrl = $this->get('portal_webhook_url', null, null, '');
        if (!$secret || !$webhookUrl) {
            return;
        }

        $signature = hash_hmac('sha256', $surveyId . ':' . $token, $secret);
        $payload = json_encode([
            'sid' => $surveyId,
            'token' => $token,
            'signature' => $signature,
        ]);

        $this->sendWebhook($webhookUrl, $payload);
    }

    /**
     * Erzwingt die Pflicht-Einstellungen der Feedback-Umfragen unmittelbar vor
     * der Aktivierung -- also bevor LimeSurvey die Antworttabelle anlegt, deren
     * Spalten (u.a. "token") von "anonymized" abhaengen (siehe
     * docs/limesurvey-analyse.md Abschnitt 3). Das Portal setzt diese Werte
     * bereits beim Uebertragen/Kopieren der Vorlage; dies ist die zusaetzliche
     * Absicherung, falls jemand sie in der LimeSurvey-UI manuell aendert.
     */
    public function beforeSurveyActivate()
    {
        $event = $this->getEvent();
        $surveyId = (int) $event->get('surveyId');
        $survey = Survey::model()->findByPk($surveyId);
        if ($survey === null) {
            return;
        }

        $mandatory = [
            'anonymized' => 'Y',
            'datestamp' => 'N',
            'ipaddr' => 'N',
            'printanswers' => 'Y',
            'tokenanswerspersistence' => 'Y',
            'alloweditaftercompletion' => 'N',
        ];

        $changed = false;
        foreach ($mandatory as $key => $value) {
            if ($survey->$key !== $value) {
                $survey->$key = $value;
                $changed = true;
            }
        }
        if ($changed) {
            $survey->save();
        }
    }

    /**
     * Kleiner, abhaengigkeitsfreier cURL-POST (kein Guzzle im LimeSurvey-Kern
     * vorausgesetzt). Fehler werden bewusst nur geloggt: ein ausgefallener
     * Webhook darf die Umfrage-Abgabe fuer die Teilnehmenden nicht blockieren
     * -- das Portal hat mit dem Polling-Fallback (list_participants) ohnehin
     * eine zweite Absicherung (siehe TASKS.md Phase 4).
     */
    private function sendWebhook($url, $payload)
    {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 5);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 3);
        curl_exec($ch);
        if (curl_errno($ch)) {
            error_log('FeedbackBridge: Webhook fehlgeschlagen: ' . curl_error($ch));
        }
        curl_close($ch);
    }
}
