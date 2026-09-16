
"""
Django settings for jobconnect project.

Django 5.2.17

Production architecture:
React + Nginx/Reverse Proxy + Django + PostgreSQL

Development values are loaded from .env.
"""

from pathlib import Path
from datetime import timedelta
import os

from decouple import config


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================================================
# SECURITY
# =========================================================

# IMPORTANT:
# Store the real production SECRET_KEY in .env.
SECRET_KEY = config(
    "SECRET_KEY",
    default="",
)

# Never use DEBUG=True in production.
DEBUG = config(
    "DEBUG",
    default=False,
    cast=bool,
)


# =========================================================
# ALLOWED HOSTS
# =========================================================
#
# Development:
# localhost / 127.0.0.1
#
# Production:
# Replace with your real domain.
#
# Example:
#   jobconnect.com
#   www.jobconnect.com
#
# If testing through your Windows LAN IP, add that IP too.
# Example:
#   192.168.1.10
#
# =========================================================

ALLOWED_HOSTS = [
    host.strip()
    for host in config(
        "ALLOWED_HOSTS",
        default="localhost,127.0.0.1,dan-convention-commands-pay.trycloudflare.com   "
    ).split(",")
    if host.strip()
]


# =========================================================
# HTTPS / PRODUCTION SECURITY
# =========================================================
#
# IMPORTANT:
# These settings should be enabled when JobConnect is
# actually being served through HTTPS.
#
# For your final public deployment:
#   HTTPS = True
#
# During local HTTP development:
#   set SECURE_SSL_REDIRECT=False
#   set DEBUG=True
#
# =========================================================

SECURE_SSL_REDIRECT = config(
    "SECURE_SSL_REDIRECT",
    default=True,
    cast=bool,
)

SESSION_COOKIE_SECURE = config(
    "SESSION_COOKIE_SECURE",
    default=True,
    cast=bool,
)

CSRF_COOKIE_SECURE = config(
    "CSRF_COOKIE_SECURE",
    default=True,
    cast=bool,
)

# Nginx / reverse proxy sends this header after HTTPS.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

# Prevent clickjacking.
X_FRAME_OPTIONS = "DENY"

# Browser content-type sniffing protection.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Referrer policy.
SECURE_REFERRER_POLICY = (
    "strict-origin-when-cross-origin"
)


# =========================================================
# HSTS
# =========================================================
#
# Enable this only after HTTPS is confirmed to work correctly.
#
# 31536000 = 1 year
#
# =========================================================

SECURE_HSTS_SECONDS = config(
    "SECURE_HSTS_SECONDS",
    default=0,
    cast=int,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
    cast=bool,
)

SECURE_HSTS_PRELOAD = config(
    "SECURE_HSTS_PRELOAD",
    default=False,
    cast=bool,
)


# =========================================================
# APPLICATION DEFINITION
# =========================================================

INSTALLED_APPS = [

    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",

    # Project apps
    "adminpanel",
    "jobseeker",
    "employer",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # CORS
    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL CONFIGURATION
# =========================================================

ROOT_URLCONF = "jobconnect.urls"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND":
            "django.template.backends.django.DjangoTemplates",

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


# =========================================================
# WSGI
# =========================================================

WSGI_APPLICATION = (
    "jobconnect.wsgi.application"
)


# =========================================================
# DATABASE
# POSTGRESQL
# =========================================================
#
# Production credentials MUST come from .env.
#
# Do not use the PostgreSQL `postgres` superuser for the
# application in final production.
#
# =========================================================

DATABASES = {

    "default": {

        "ENGINE":
            "django.db.backends.postgresql",

        "NAME":
            config(
                "POSTGRES_DB",
                default="jobconnect_db",
            ),

        "USER":
            config(
                "POSTGRES_USER",
                default="jobconnect_user",
            ),

        "PASSWORD":
            config(
                "POSTGRES_PASSWORD",
                default="",
            ),

        "HOST":
            config(
                "POSTGRES_HOST",
                default="127.0.0.1",
            ),

        "PORT":
            config(
                "POSTGRES_PORT",
                default="5432",
            ),
    }
}


# =========================================================
# DJANGO REST FRAMEWORK
# =========================================================

REST_FRAMEWORK = {

    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}


# =========================================================
# JWT CONFIGURATION
# =========================================================

SIMPLE_JWT = {

    "ACCESS_TOKEN_LIFETIME":
        timedelta(
            minutes=config(
                "JWT_ACCESS_MINUTES",
                default=60,
                cast=int,
            )
        ),

    "REFRESH_TOKEN_LIFETIME":
        timedelta(
            days=config(
                "JWT_REFRESH_DAYS",
                default=7,
                cast=int,
            )
        ),

    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),
}


# =========================================================
# CORS
# =========================================================
#
# IMPORTANT:
# In production, the best setup is:
#
# React:
#   https://yourdomain.com
#
# Django API:
#   https://yourdomain.com/api/
#
# In that same-domain setup, CORS becomes mostly unnecessary.
#
# Keep this configurable so you can use separate frontend
# and backend domains when required.
# =========================================================

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:5173,http://127.0.0.1:5173,https://dan-convention-commands-pay.trycloudflare.com",
    ).split(",")
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = config(
    "CORS_ALLOW_CREDENTIALS",
    default=True,
    cast=bool,
)

CORS_ALLOW_HEADERS = [

    "accept",

    "accept-encoding",

    "authorization",

    "content-type",

    "dnt",

    "origin",

    "user-agent",

    "x-csrftoken",

    "x-requested-with",
]


# =========================================================
# CSRF
# =========================================================

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config(
        "CSRF_TRUSTED_ORIGINS",
        default="http://localhost:5173,http://127.0.0.1:5173,https://dan-convention-commands-pay.trycloudflare.com",
    ).split(",")
    if origin.strip()
]


# =========================================================
# EMAIL
# =========================================================

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = config(
    "EMAIL_HOST",
    default="smtp.gmail.com",
)

EMAIL_PORT = config(
    "EMAIL_PORT",
    default=587,
    cast=int,
)

EMAIL_USE_TLS = config(
    "EMAIL_USE_TLS",
    default=True,
    cast=bool,
)

EMAIL_HOST_USER = config(
    "EMAIL_HOST_USER",
    default="",
)

EMAIL_HOST_PASSWORD = config(
    "EMAIL_HOST_PASSWORD",
    default="",
)

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=EMAIL_HOST_USER,
)


# =========================================================
# GOOGLE LOGIN
# =========================================================

GOOGLE_CLIENT_ID = config(
    "GOOGLE_CLIENT_ID",
    default="",
)


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [

    {
        "NAME":
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.MinimumLengthValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.CommonPasswordValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# WHITENOISE
# =========================================================

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)


# =========================================================
# MEDIA FILES
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)
