from datetime import datetime, timezone
import logging
from typing import Optional

import requests

from megatron import settings
from megatron.connections.slack import SlackConnection
from megatron.connections.actions import Action, ActionType
from megatron.models import (
    MegatronIntegration,
    MegatronChannel,
    CustomerWorkspace,
    PlatformUser,
    PlatformAgent,
)


LOGGER = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, integration: MegatronIntegration) -> None:
        self.integration = integration

    def get_connection(self, as_user=True):
        return SlackConnection(self.integration.connection_token, as_user=as_user)

    def get_interpreter(self):
        # TODO: Make dynamic
        from megatron.interpreters.slack import api

        return api

    def get_or_create_user_by_id(self, user_id: str) -> Optional[PlatformAgent]:
        try:
            platform_agent = PlatformAgent.objects.get(
                platform_id=user_id, integration=self.integration
            )
        except PlatformAgent.DoesNotExist:
            connection = self.get_connection()
            action = Action(ActionType.GET_USER_INFO, {"user_id": user_id})
            response = connection.take_action(action)
            if response.get("ok"):
                profile = response["user"]["profile"]
                platform_agent = PlatformAgent.objects.create(
                    platform_id=user_id,
                    integration=self.integration,
                    profile_image=profile["image_72"],
                    username=response["user"]["name"],
                    display_name=profile.get("display_name"),
                    real_name=profile.get("real_name"),
                )
            else:
                LOGGER.error(
                    "Failed to obtain or create platform agent data.",
                    extra={"platform_user_id": user_id, "error": response["error"]},
                )
                platform_agent = None
        return platform_agent


class WorkspaceService:
    def __init__(self, workspace: CustomerWorkspace) -> None:
        self.workspace = workspace

    def get_connection(self, as_user=True):
        return SlackConnection(self.workspace.connection_token, as_user=as_user)

    def refresh_user_data(self):
        for platform_user in self.workspace.platformuser_set.all():
            connection = self.get_connection()

            action = Action(
                ActionType.GET_USER_INFO, {"user_id": platform_user.platform_id}
            )
            response = connection.take_action(action)
            if response.get("ok"):
                profile = response["user"]["profile"]
                platform_user.profile_image = profile["image_72"]
                platform_user.username = profile["display_name"]
                platform_user.save()
            else:
                LOGGER.warning(
                    "Failed to update platform user data.",
                    extra={
                        "platform_user_id": platform_user.id,
                        "error": response["error"],
                    },
                )

    def get_or_create_user_by_id(self, user_id: str) -> Optional[PlatformUser]:
        try:
            platform_user = PlatformUser.objects.get(
                platform_id=user_id, workspace=self.workspace
            )
        except PlatformUser.DoesNotExist:
            connection = self.get_connection()
            action = Action(ActionType.GET_USER_INFO, {"user_id": user_id})
            response = connection.take_action(action)
            if response.get("ok"):
                profile = response["user"]["profile"]
                platform_user = PlatformUser.objects.create(
                    platform_id=user_id,
                    workspace=self.workspace,
                    profile_image=profile["image_72"],
                    username=response["user"]["name"],
                    display_name=profile.get("display_name"),
                    real_name=profile.get("real_name"),
                )
            else:
                LOGGER.exception(
                    "Failed to obtain or create platform user data.",
                    extra={"platform_user_id": user_id, "error": response["error"]},
                )
                return None
        return platform_user


class MegatronChannelService:
    def __init__(self, channel: MegatronChannel) -> None:
        self.channel = channel

    def unarchive(self):
        connection = IntegrationService(
            self.channel.megatron_integration
        ).get_connection()
        response = connection.unarchive_channel(self.channel.platform_channel_id)
        if response["ok"]:
            self.channel.last_message_sent = datetime.now(timezone.utc)
            self.channel.is_archived = False
            self.channel.save()
        return response

    def archive(self):
        connection = IntegrationService(
            self.channel.megatron_integration
        ).get_connection()
        response = connection.archive_channel(self.channel.platform_channel_id)
        if response["ok"]:
            self.channel.is_archived = True
            self.channel.save()
        elif response["error"] == "already_archived":
            self.channel.is_archived = True
            self.channel.save()
        return response

    def change_pause_state(self, pause_state, user_channel_id=None):
        """
        Send a request to the main server to change the channel pause state, besides updating the state in megatron
        The user and bot MD channel ID is necessary, so if it's not sent a request to slack will be made to know it.
        """
        if not user_channel_id:
            connection = WorkspaceService(self.channel.workspace).get_connection()
            user_channel_id = connection.open_im(self.channel.platform_user_id)[
                "channel"
            ]["id"]
        data = {
            "megatron_verification_token": settings.MEGATRON_VERIFICATION_TOKEN,
            "command": "pause",
            "channel_id": user_channel_id,
            "team_id": self.channel.workspace.platform_id,
            "paused": pause_state,
        }

        response = requests.post(self.channel.megatron_user.command_url, json=data)
        # TODO: This response is 200 even on failure to find user
        if response.status_code == 200:
            self.channel.is_paused = pause_state
            self.channel.save()
        return response
