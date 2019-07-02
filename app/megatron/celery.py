import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "megatron.settings")
worker_mode = os.environ.get("WORKER_MODE", "non-celery")
REDIS_URL = os.environ["REDIS_URL"]


class Config:
    broker_url = REDIS_URL
    result_backend = REDIS_URL
    accept_content = ["pickle", "application/json"]
    task_serializer = "json"
    result_serializer = "json"
    enable_utc = True
    # BEWARE: Manually importing tasks
    imports = ["megatron.scheduled_tasks"]
    ignore_result = True
    task_routes = ([("megatron.*", {"queue": "megatron"})],)


app = Celery("megatron")
app.config_from_object(Config)

# THIS MUST BE SET TO THE MAXIMUM DELAY AMOUNT THAT WILL EVER HAPPEN
# VIA CELERY
app.conf.broker_transport_options = {"visibility_timeout": (60 * 60 * 24 * 14) + 1}

CRONTABS = {
    "minutely": crontab(),
    "hourly": crontab(
        minute="0", hour="*", day_of_week="*", day_of_month="*", month_of_year="*"
    ),
    "daily": crontab(
        minute="0", hour="0", day_of_week="*", day_of_month="*", month_of_year="*"
    ),
    "weekly": crontab(minute="0", hour="0", day_of_week="mon"),
    "monthly": crontab(minute="0", hour="0", day_of_month="1"),
    "five-minute-ly": crontab(
        minute="*/5", hour="*", day_of_week="*", day_of_month="*", month_of_year="*"
    ),
}


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    app.conf.beat_schedule = {
        "Refresh Platform User Data": {
            "task": "megatron.scheduled_tasks",
            "schedule": CRONTABS["daily"],
            "options": {"queue": "megatron"},
        },
        "Remind Unpause Channel": {
            "task": "megatron.scheduled_tasks.unpause_reminder",
            "schedule": CRONTABS["minutely"],
            "options": {"queue": "megatron"},
        },
        "Archive Channels": {
            "task": "megatron.scheduled_tasks.archive_channels",
            "schedule": CRONTABS["daily"],
            "options": {"queue": "megatron"},
        },
    }
