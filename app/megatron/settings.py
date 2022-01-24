import os
import re
from megatron.statics import NotificationChannels

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["MEGATRON_DJANGO_SECRET"]

ROOT_URLCONF = "megatron.urls"
CHANNEL_PREFIX = os.environ["CHANNEL_PREFIX"]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_celery_beat",
    "rest_framework.authtoken",
    "megatron",
]

# Format: `megatron-ENVIRONMENT`
MEGATRON_APP_MODE = os.environ["MEGATRON_APP_MODE"]
DEBUG = MEGATRON_APP_MODE == "megatron-dev"

STATIC_ROOT = os.path.join(BASE_DIR, "static/")
STATIC_URL = "/static/"

# TODO: Switch to secure slack signing token
MEGATRON_VERIFICATION_TOKEN = os.environ["MEGATRON_VERIFICATION_TOKEN"]
REDIS_URL = os.environ["REDIS_URL"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "megatron.authentication.MegatronTokenAuthentication",
    )
}

# ====================== Routing ======================
HOSTNAME: str = os.environ.get("HOSTNAME", "")
PORT = os.environ.get("DJANGO_PORT", "8002")

if PORT not in ["80", "43", "8000, 8002"]:
    HOSTNAME = "{}:{}".format(HOSTNAME, PORT)
FORMATTED_HOSTNAME = re.sub(r"https://", "", str(os.environ.get("HOSTNAME")))
LOAD_BALANCER_HOST = "load-balancing.teampay.co"
ALLOWED_HOSTS = {FORMATTED_HOSTNAME, LOAD_BALANCER_HOST, "0.0.0.0", "localhost"}

# ==================== Logging ========================
import dj_database_url  # noqa

DATABASES = {"default": dj_database_url.config()}

# ==================== AWS ========================
AWS_ACCESS_KEY = os.environ["S3_AWS_ACCESS_KEY_ID"]
AWS_SECRET_KEY = os.environ["S3_AWS_SECRET_ACCESS_KEY"]
AWS_S3_BUCKET = os.environ["AWS_S3_BUCKET"]


# ==================== Channels ========================
NOTIFICATIONS_CHANNELS = {
    NotificationChannels.notifications: os.environ.get(
        "NOTIFICATIONS_CHANNEL", "#notifications"
    ),
    NotificationChannels.operations: os.environ.get(
        "OPERATIONS_CHANNEL", "#operations"
    ),
    NotificationChannels.dev_ops: os.environ.get(
        "DEV_CRON_JOBS_CHANNEL", "#dev-cron-jobs"
    ),
    NotificationChannels.customer_service: os.environ.get(
        "CUSTOMER_SERVICE_CHANNEL", "#customer-service"
    ),
    NotificationChannels.security: os.environ.get("SECURITY_CHANNEL", "#security"),
}
