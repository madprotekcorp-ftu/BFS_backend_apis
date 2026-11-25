from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that answers 401 (not 403) when there is no session.

    DRF only returns 401 when the authenticator provides a WWW-Authenticate value.
    """

    def authenticate_header(self, request):
        return "Session"


def enforce_csrf(request):
    """Run Django's CSRF check on a view that has no authenticator (e.g. login)."""
    SessionAuthentication().enforce_csrf(request)
