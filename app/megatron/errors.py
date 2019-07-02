import logging

from enum import Enum, auto
from functools import wraps
from rest_framework.response import Response
from rest_framework import status


LOGGER = logging.getLogger(__name__)


class MegatronError(Enum):
    @property
    def status_code(self):
        pass


class MegatronException(Exception):
    def __init__(self, platform_message=None):
        self.platform_message = platform_message


class ErrorResponse(Response):
    def __init__(
        self, error: MegatronError, status: status = status.HTTP_200_OK, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.status = status
        self.data = {"ok": False, "error": error.name}


class BroadcastError(MegatronError):
    missing_text = auto()
    missing_organization_id = auto()
    missing_bot_type = auto()
    malformed_broadcast = auto()
    user_not_found = auto()


class BroadcastWarnings(MegatronError):
    unknown_organization = auto()
    unknown_bot_type = auto()
    unknown_user_scope = auto()


def raise_error(error: MegatronError, status: status):
    LOGGER.exception(error.name)
    return ErrorResponse(error, status)


def catch_megatron_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
        except MegatronException as exc:
            LOGGER.exception(exc)
            return {"ok": False, "error": "Unrecognized error.", "status": 500}
        return response

    return wrapper
