import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-do-not-use-in-prod")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "noctua.core",
]

MIDDLEWARE = [
    "noctua.core.cors.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

NOCTUA_CORS_ALLOWED_ORIGINS = os.environ.get(
    "NOCTUA_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)

ROOT_URLCONF = "noctua.urls"
WSGI_APPLICATION = "noctua.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "noctua",
        "USER": "noctua",
        "PASSWORD": "noctua",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TIME_LIMIT = 60 * 60  # 1h hard ceiling, per-mission override
CELERY_TASK_SOFT_TIME_LIMIT = 30 * 60

NOCTUA_API_TOKEN = os.environ.get("NOCTUA_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID = os.environ.get("COMPOSIO_USER_ID", "noctua_default")
NOCTUA_ARCHIVE_DIR = BASE_DIR / "archive"
NOCTUA_TOOLS_DIR = BASE_DIR / "tools"

# In tests, run Celery tasks inline so we don't need a worker.
# Driven by the NOCTUA_CELERY_EAGER env var (set by pytest-django via DJANGO_SETTINGS_MODULE auto-load).
if os.environ.get("NOCTUA_CELERY_EAGER") == "1":
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
