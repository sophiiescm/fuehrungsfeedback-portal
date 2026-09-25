"""OIDC-SSO-Modul (z.B. Entra ID), per ENV aktivierbar (OIDC_ENABLED=true).

Nur aktiv, wenn oidc_enabled gesetzt ist. Ausserhalb dieses Moduls darf nichts
von Authlib importiert werden, damit ein deaktiviertes OIDC keine zusaetzlichen
Abhaengigkeiten zur Laufzeit braucht.
"""

from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

_oauth: OAuth | None = None


def get_oauth_client() -> OAuth:
    global _oauth
    settings = get_settings()
    if not settings.oidc_enabled:
        raise RuntimeError("OIDC ist per Konfiguration deaktiviert (OIDC_ENABLED=false)")
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="oidc",
            server_metadata_url=f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth
