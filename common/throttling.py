from rest_framework.throttling import BaseThrottle, SimpleRateThrottle


def client_ip(request):
    """Client IP, honouring REST_FRAMEWORK["NUM_PROXIES"] for X-Forwarded-For."""
    return BaseThrottle().get_ident(request)


class EnquiryThrottle(SimpleRateThrottle):
    """Public enquiry form: 5 submissions per IP per hour."""

    scope = "enquiry"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
