"""Django settings for the DiagnoSure backend."""
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# For a student/demo project this default is fine. In production, load from env.
SECRET_KEY = os.environ.get(
    "DIAGNOSURE_SECRET_KEY", "dev-insecure-change-me-in-production"
)
ON_VERCEL = bool(os.environ.get("VERCEL"))
DEBUG = os.environ.get("DIAGNOSURE_DEBUG", "0" if ON_VERCEL else "1") == "1"
ALLOWED_HOSTS = ["*"]  # demo; restrict in production
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "diagnosure.urls"

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

WSGI_APPLICATION = "diagnosure.wsgi.application"

SQLITE_PATH = BASE_DIR / "db.sqlite3"

# Vercel's filesystem is read-only except /tmp, so copy the bundled SQLite
# database there to allow writes. Data in /tmp is NOT persistent across
# deployments/cold starts - set DATABASE_URL to a hosted Postgres for that.
if ON_VERCEL:
    tmp_db = Path("/tmp/db.sqlite3")
    if not tmp_db.exists() and SQLITE_PATH.exists():
        shutil.copy(SQLITE_PATH, tmp_db)
    SQLITE_PATH = tmp_db

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": SQLITE_PATH,
    }
}

if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES["default"] = dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# The frontend is opened from the file system / a static server, so allow all
# origins for this demo. In production list only your real frontend origin.
CORS_ALLOW_ALL_ORIGINS = True
