import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG", "true").lower() in ("true", "1", "yes")

if DEBUG:
    SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
else:
    SECRET_KEY = os.environ["SECRET_KEY"]  # crash if missing in production

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "config",
    "apps.accounts",
    "apps.core",
    "apps.catalog",
    "apps.provenance",
    "apps.media",
    "constance",
    "constance.backends.database",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.SvelteKitWhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: Postgres via DATABASE_URL, SQLite fallback for dev
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    ),
}

# Server-side cache: file-based so all gunicorn workers + management commands
# share the same cache via the filesystem. Invalidated explicitly on data changes.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "cache",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Media storage (S3-compatible file storage provider) ───────────
MEDIA_PUBLIC_BASE_URL = os.environ.get("MEDIA_PUBLIC_BASE_URL", "/media/")
MEDIA_URL = MEDIA_PUBLIC_BASE_URL

if os.environ.get("MEDIA_STORAGE_BUCKET"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    AWS_STORAGE_BUCKET_NAME = os.environ["MEDIA_STORAGE_BUCKET"]
    AWS_S3_REGION_NAME = os.environ.get("MEDIA_STORAGE_REGION", "auto")
    AWS_S3_ENDPOINT_URL = os.environ["MEDIA_STORAGE_ENDPOINT"]
    AWS_ACCESS_KEY_ID = os.environ["MEDIA_STORAGE_ACCESS_KEY"]
    AWS_SECRET_ACCESS_KEY = os.environ["MEDIA_STORAGE_SECRET_KEY"]
else:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }
    MEDIA_ROOT = BASE_DIR / "media"

# Allow large image uploads (20MB) to reach our view for proper error
# messages. FILE_UPLOAD_MAX_MEMORY_SIZE stays at default (2.5MB) — larger
# files spill to disk temp files, which is fine.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Frontend static build (SvelteKit) ──────────────────────────────
# In Docker: /app/frontend_build (copied from multi-stage build)
# In local dev: ../frontend/build (if it exists; optional for dev)
FRONTEND_BUILD_DIR = BASE_DIR / "frontend_build"
if not FRONTEND_BUILD_DIR.is_dir():
    _local_build = BASE_DIR.parent / "frontend" / "build"
    if _local_build.is_dir():
        FRONTEND_BUILD_DIR = _local_build

# Serve SvelteKit build assets at the URL root via WhiteNoise middleware.
# Only files that physically exist are served; all other requests fall
# through to Django URL routing (API, admin, and catch-all).
if FRONTEND_BUILD_DIR.is_dir():
    WHITENOISE_ROOT = FRONTEND_BUILD_DIR
elif not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        f"Frontend build directory not found at {FRONTEND_BUILD_DIR}. "
        "Run the Docker build or `cd frontend && pnpm build`."
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "level": "ERROR",
        },
        "django.db.backends": {
            "level": "WARNING",
        },
    },
}

# CSRF — allow JS to read the cookie for X-CSRFToken header
CSRF_COOKIE_HTTPONLY = False
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

# Secure cookies in production
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True

# ---------------------------------------------------------------------------
# Constance (runtime-configurable settings)
# ---------------------------------------------------------------------------
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
if "pytest" in sys.modules:
    CONSTANCE_BACKEND = "constance.backends.memory.MemoryBackend"

DISPLAY_POLICY_CHOICES = (
    ("show-all", "☠️ Show All Content — includes Not Allowed (e.g. IPDB images)"),
    ("include-unknown", "⚠️ Include Unknown License Content (e.g. OPDB images)"),
    ("licensed-only", "✅ Show Only Licensed Content — no OPDB or IPDB images"),
)

CONSTANCE_CONFIG = {
    "CONTENT_DISPLAY_POLICY": (
        "licensed-only",
        "Controls which content is shown based on license status",
        str,
    ),
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "display_policy_select": [
        "django.forms.fields.ChoiceField",
        {"widget": "django.forms.Select", "choices": DISPLAY_POLICY_CHOICES},
    ],
}

CONSTANCE_CONFIG["CONTENT_DISPLAY_POLICY"] = (
    "licensed-only",
    "Controls which content is shown based on license status",
    "display_policy_select",
)

CONSTANCE_CONFIG_FIELDSETS = (("Content Display", ("CONTENT_DISPLAY_POLICY",)),)
