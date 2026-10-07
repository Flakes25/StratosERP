"""Settings changes for local + cloud use. Paste into your settings.py.

Replace the matching existing lines instead of duplicating them.
Everything reads from environment variables, so the same code runs on your laptop
(SQLite, DEBUG on) and in the cloud (PostgreSQL, DEBUG off).
"""
import os

# ---- core ---------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# ---- INSTALLED_APPS: make sure it contains "core" ------------------------

# ---- MIDDLEWARE: add WhiteNoise right after SecurityMiddleware -----------
#   "django.middleware.security.SecurityMiddleware",
#   "whitenoise.middleware.WhiteNoiseMiddleware",      # <- add this line

# ---- TEMPLATES -> OPTIONS -> context_processors: add this line ------------
#   "core.context_processors.roles",

# ---- database: PostgreSQL when DATABASE_URL is set, SQLite otherwise -------
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)}
# else: keep the DATABASES block Django generated (SQLite)

# ---- static files ------------------------------------------------------------
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {  # Django 4.2+. On older versions use STATICFILES_STORAGE instead.
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---- authentication ------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True   # always start at the login page

# ---- telemetry intake API ----------------------------------------------------------
TELEMETRY_API_KEY = os.environ.get("TELEMETRY_API_KEY", "")

# ---- production hardening (only when DEBUG is off) ---------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
