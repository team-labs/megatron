from enum import Enum

from megatron.models import CustomerWorkspace, PlatformType
from .connections import slack
from . import authentication


class BotType(Enum):
    slack = 1

    def get_bot_connection(self, organization):
        token = authentication.get_organization_token(organization)
        if self == BotType.slack:
            return slack.SlackConnection(token)
        else:
            raise Exception("Invalid bot type provided.")

    def get_bot_connection_from_platform_id(self, platform_id):
        if self == BotType.slack:
            platform_type = PlatformType.Slack.value
        workspace = CustomerWorkspace.objects.get(
            platform_id=platform_id,
            platform_type=platform_type
        )
        if self == BotType.slack:
            return slack.SlackConnection(workspace.connection_token)
        else:
            raise Exception("Invalid bot type provided.")
