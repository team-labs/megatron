import os
import re
from megatron.statics import NotificationChannels

DEBUG = True
SECRET_KEY = '4l0ngs3cr3tstr1ngw3lln0ts0lj0ngw41tn0w1tsl0ng3n0ugh'
ROOT_URLCONF = 'megatron.urls'
CHANNEL_PREFIX = os.environ['CHANNEL_PREFIX']
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLED_APPS = [
     'django.contrib.contenttypes',
     'django.contrib.auth',
     'django_celery_beat',
     'rest_framework.authtoken',
     'megatron'
]

MEGATRON_APP_MODE = os.environ.get('MEGATRON_APP_MODE', 'dev')

STATIC_ROOT = os.path.join(BASE_DIR, "static/")
STATIC_URL = "/static/"

# TODO: Switch to secure slack signing token
MEGATRON_VERIFICATION_TOKEN = os.environ['MEGATRON_VERIFICATION_TOKEN']
REDIS_URL = os.environ['REDIS_URL']

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'megatron.authentication.MegatronTokenAuthentication',
    )
}

# ====================== Routing ======================
HOSTNAME: str = os.environ.get('HOSTNAME', '')
PORT = os.environ.get('DJANGO_PORT', "8002")

if PORT not in ["80", "43", "8000, 8002"]:
    HOSTNAME = "{}:{}".format(HOSTNAME, PORT)
FORMATTED_HOSTNAME = re.sub(r'https://', '', str(os.environ.get('HOSTNAME')))
ALLOWED_HOSTS = {
    FORMATTED_HOSTNAME,
    '0.0.0.0',
    'localhost',
}




# ==================== AWS ========================
AWS_ACCESS_KEY = os.environ['S3_AWS_ACCESS_KEY_ID']
AWS_SECRET_KEY = os.environ['S3_AWS_SECRET_ACCESS_KEY']
AWS_S3_BUCKET = os.environ['AWS_S3_BUCKET']


NOTIFICATIONS_CHANNELS = {
    NotificationChannels.notifications: os.environ.get('NOTIFICATIONS_CHANNEL',
                                                       '#notifications'),
    NotificationChannels.operations: os.environ.get('OPERATIONS_CHANNEL', '#operations'),
    NotificationChannels.dev_ops: os.environ.get('DEV_CRON_JOBS_CHANNEL', '#dev-cron-jobs'),
    NotificationChannels.customer_service: os.environ.get('CUSTOMER_SERVICE_CHANNEL', '#customer-service'),
    NotificationChannels.security: os.environ.get('SECURITY_CHANNEL', '#security')
}
