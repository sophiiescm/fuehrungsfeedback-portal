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

    feedbackbridge_hmac_secret: str = "change_me_dev_hmac_secret"

    # OIDC SSO
    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_url: str = "http://localhost:5173/auth/callback"

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "feedback-portal@example.test"

    # KI-Zusammenfassung
    ai_provider: str = "none"  # none | openai_compatible | anthropic
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None

    access_token_expire_minutes: int = 60 * 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
