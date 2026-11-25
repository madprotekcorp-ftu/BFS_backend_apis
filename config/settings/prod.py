from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
X_FRAME_OPTIONS = "DENY"
# HSTS preload is a hard-to-undo, domain-wide commitment: BFS decides once the domain is final.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Nginx serves document bytes after Django has checked auth.
DOCUMENTS_USE_X_ACCEL = env.bool("DOCUMENTS_USE_X_ACCEL", default=True)

# Swagger and the Django admin are off in production unless explicitly enabled
# (set API_DOCS_ENABLED=True on staging).
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=False)
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=False)
