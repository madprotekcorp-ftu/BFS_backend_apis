import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="bfs-test-media-"))
DOCUMENTS_USE_X_ACCEL = False
API_DOCS_ENABLED = True
DJANGO_ADMIN_ENABLED = False
