from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    secret_key: str = "change_me_dev_secret_key_please_rotate"

    database_url: str = "postgresql+psycopg://portal:portal_dev_password@localhost:5432/portal"

    # Anonymitaetsschwellen (CLAUDE.md: nie < 3)
    min_team_size_for_invitation: int = 3
    min_responses_for_report: int = 3

    # LimeSurvey RemoteControl
    limesurvey_rc_api_url: str = "http://localhost:8080/index.php/admin/remotecontrol"
    limesurvey_rc_user: str = "admin"
    limesurvey_rc_password: str = "admin_dev_password"
    # Oeffentliche Basis-URL, unter der Teilnehmende (Browser) LimeSurvey erreichen
    # (kann von limesurvey_rc_api_url abweichen, das intern das Docker-Netzwerk nutzt)
    limesurvey_url_public: str = "http://localhost:8080"
    portal_public_url: str = "http://localhost:5173"

    feedbackbridge_hmac_secret: str = "change_me_dev_hmac_secret"

    # OIDC SSO
    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_url: str = "http://localhost:5173/auth/callback"

    oidc_person_claim: str = "email"  # email | preferred_username | upn | employeeid ...
    oidc_person_field: str = "email"  # email | personalnummer

    # Trusted-App-SSO (Mitarbeiter-App reicht kurzlebige signierte Assertion durch)
    app_sso_secret: str | None = None  # leer = deaktiviert
    app_sso_issuer: str = "mitarbeiter-app"
    app_sso_max_lifetime_seconds: int = 120

    # SuccessFactors / SAP OData
    odata_base_url: str | None = None
    odata_user: str | None = None
    odata_password: str | None = None

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "feedback-portal@example.test"
    smtp_user: str | None = None  # z. B. Exchange Online: smtp.office365.com:587 + STARTTLS
    smtp_password: str | None = None
    smtp_starttls: bool = False

    # KI-Zusammenfassung
    ai_provider: str = "none"  # none | openai_compatible | anthropic
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None

    # Loeschfristen (Tage), siehe app/services/retention.py
    retention_survey_days: int = 90
    retention_notification_days: int = 180
    retention_login_code_days: int = 90
    retention_audit_days: int = 365

    access_token_expire_minutes: int = 60 * 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
