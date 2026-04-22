import os
import sys
from pathlib import Path
from typing import Any

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG", "true").lower() in ("true", "1", "yes")

if DEBUG:
    SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
else:
    SECRET_KEY = os.environ["SECRET_KEY"].strip()  # crash if missing in production

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
# SSR and health-check traffic reaches Django on 127.0.0.1 inside the
# container, so localhost must always be allowed regardless of the env var.
for _host in ("localhost", "127.0.0.1"):
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

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
    "apps.citation",
    "apps.provenance",
    "apps.media",
    "constance",
    "constance.backends.database",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
MEDIA_PUBLIC_BASE_URL = os.environ.get("MEDIA_PUBLIC_BASE_URL", "/media/").strip()
if not MEDIA_PUBLIC_BASE_URL.endswith("/"):
    raise ImproperlyConfigured(
        f"MEDIA_PUBLIC_BASE_URL must end with a slash (got {MEDIA_PUBLIC_BASE_URL!r})."
    )
MEDIA_URL = MEDIA_PUBLIC_BASE_URL

if os.environ.get("MEDIA_STORAGE_BUCKET"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    AWS_STORAGE_BUCKET_NAME = os.environ["MEDIA_STORAGE_BUCKET"].strip()
    AWS_S3_REGION_NAME = os.environ.get("MEDIA_STORAGE_REGION", "auto").strip()
    AWS_S3_ENDPOINT_URL = os.environ["MEDIA_STORAGE_ENDPOINT"].strip()
    AWS_ACCESS_KEY_ID = os.environ["MEDIA_STORAGE_ACCESS_KEY"].strip()
    AWS_SECRET_ACCESS_KEY = os.environ["MEDIA_STORAGE_SECRET_KEY"].strip()
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

# ── WorkOS AuthKit ────────────────────────────────────────────────
WORKOS_API_KEY = os.environ.get("WORKOS_API_KEY", "").strip()
WORKOS_CLIENT_ID = os.environ.get("WORKOS_CLIENT_ID", "").strip()
WORKOS_REDIRECT_URI = os.environ.get(
    "WORKOS_REDIRECT_URI", "http://localhost:5173/api/auth/callback/"
).strip()

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.WorkOSBackend",
    "django.contrib.auth.backends.ModelBackend",  # Django admin password login
]

# ── Sessions ─────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90  # 90 days
SESSION_SAVE_EVERY_REQUEST = True  # sliding window — reset expiry on each request

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
    # TLS is terminated by Railway's edge proxy and (in the container) by
    # Caddy.  Django never receives external traffic directly, so SSL
    # redirect and proxy-header sniffing are unnecessary.  Keeping them
    # would break internal callers (SSR, health checks) that reach Django
    # over plain HTTP on 127.0.0.1.

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

CONSTANCE_CONFIG: dict[str, Any] = {
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
