from typing import NamedTuple
from enum import Enum


class RequestData(NamedTuple):
    channel_id: str
    user_id: str
    response_url: str


class NotificationChannels(Enum):
    notifications = 0
    operations = 1
    dev_ops = 2
    customer_service = 3
    security = 4
