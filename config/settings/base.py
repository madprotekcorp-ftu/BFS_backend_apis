"""Settings shared by every environment. Every value comes from environment variables."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "common",
    "apps.accounts",
    "apps.catalog",
    "apps.leads",
    "apps.employees",
    "apps.imports",
    "apps.documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database & cache ---------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

# Throttle counters live in a database cache table so every Gunicorn worker
# shares them. Create it once with: python manage.py createcachetable
if env("CACHE_URL", default=""):
    CACHES = {"default": env.cache("CACHE_URL")}
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "bfs_cache",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth, sessions, CSRF -----------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours from login
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default="") or None

CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
CSRF_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

# --- I18N / time --------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = True  # stored in UTC, rendered in TIME_ZONE

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Documents & imports ------------------------------------------------------

_private_root = Path(env("PRIVATE_MEDIA_ROOT", default="private_media"))
PRIVATE_MEDIA_ROOT = _private_root if _private_root.is_absolute() else (BASE_DIR / _private_root).resolve()
DOCUMENT_MAX_SIZE_MB = env.float("DOCUMENT_MAX_SIZE_MB", default=10)
DOCUMENTS_USE_X_ACCEL = env.bool("DOCUMENTS_USE_X_ACCEL", default=False)
DOCUMENTS_X_ACCEL_PREFIX = "/protected-documents/"

IMPORT_MAX_ROWS = env.int("IMPORT_MAX_ROWS", default=5000)
IMPORT_MAX_FILE_SIZE_MB = 5
IMPORT_PREVIEW_TTL_HOURS = 24

# --- Django REST Framework ----------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"],
    "DEFAULT_RENDERER_CLASSES": ["common.renderers.EnvelopeJSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"enquiry": env("ENQUIRY_THROTTLE_RATE", default="5/hour")},
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
    # The import template uses ?format=csv|xlsx, so DRF must not treat
    # "format" as a renderer override.
    "URL_FORMAT_OVERRIDE": None,
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%:z",
    "DATE_FORMAT": "%Y-%m-%d",
}

API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=DEBUG)
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=DEBUG)

SPECTACULAR_SETTINGS = {
    "TITLE": "BFS Phase 1 API",
    "VERSION": "1.0.0",
    "DESCRIPTION": (
        "Backend for the Bright Financial Solution website enquiry form and admin Lead "
        "Management System.\n\n"
        "**Auth:** call `GET /api/auth/csrf/`, then send `X-CSRFToken` on every POST, PATCH "
        "and DELETE. Admin endpoints use the session cookie set by `POST /api/auth/login/`.\n\n"
        "**Import policy**\n"
        "1. Required columns: `customer_name`, `mobile`, `service`. Header matching is "
        "case-insensitive and trims spaces.\n"
        "2. A row is *invalid* if a required value is missing, the mobile fails validation, "
        "the service is unknown, or a date cannot be parsed.\n"
        "3. A row is a *duplicate* if its mobile already exists in the database or appeared "
        "earlier in the same file.\n"
        "4. On confirm only valid rows are imported. Invalid and duplicate rows are skipped, "
        "never partly imported and never overwrite existing leads.\n"
        "5. Imported leads get source=existing_db, status=new, created_by = the admin, "
        "import_batch = the batch.\n"
        "6. Previews older than 24 hours are cancelled by the `cleanup_import_previews` command."
    ),
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Logging ------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"mask_mobiles": {"()": "common.log_filters.MaskMobileFilter"}},
    "formatters": {"standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["mask_mobiles"],
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"level": "WARNING"},
    },
}
