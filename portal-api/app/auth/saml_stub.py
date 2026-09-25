"""SAML-Stub (vorbereitetes Modul, CLAUDE.md: 'SAML als vorbereitetes Modul oder Stub').

Es gibt aktuell keine SAML-Anforderung eines konkreten Kunden (siehe
OPEN_QUESTIONS.md: SSO-Anbieter ist als OIDC-kompatibel angenommen). Damit ein
spaeterer Wechsel/Ergaenzung keine Architekturaenderung braucht, ist die
Schnittstelle bereits hier festgelegt, aber nicht implementiert.
"""


class SamlNotConfiguredError(NotImplementedError):
    pass


def build_saml_login_redirect_url() -> str:
    raise SamlNotConfiguredError(
        "SAML ist noch nicht implementiert. Bei Bedarf hier eine python3-saml-Integration "
        "analog zu app/auth/oidc.py ergaenzen."
    )


def handle_saml_acs_response(raw_response: bytes) -> dict:
    raise SamlNotConfiguredError(
        "SAML ist noch nicht implementiert. Bei Bedarf hier eine python3-saml-Integration "
        "analog zu app/auth/oidc.py ergaenzen."
    )
