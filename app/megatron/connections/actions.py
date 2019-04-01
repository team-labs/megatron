from typing import NamedTuple
from enum import Enum


class ActionType(Enum):
    POST_MESSAGE = 0
    POST_EPHEMERAL_MESSAGE = 1
    UPDATE_MESSAGE = 2
    OPEN_CHANNEL = 3
    GET_USER_INFO = 4
    BROADCAST = 5


class Action(NamedTuple):
    type: ActionType
    params: dict
