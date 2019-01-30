from datetime import datetime, timezone
import logging
from typing import Optional

from megatron.connections.slack import SlackConnection
from megatron.connections.actions import Action, ActionType
from megatron.models import (
    MegatronIntegration, MegatronChannel, CustomerWorkspace, PlatformUser
)


LOGGER = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, integration: MegatronIntegration) -> None:
        self.integration = integration

    def get_connection(self, as_user=True):
        return SlackConnection(
            self.integration.connection_token,
            as_user=as_user)

    def get_interpreter(self):
        # TODO: Make dynamic
        from megatron.interpreters.slack import api
        return api


class WorkspaceService:
    def __init__(self, workspace: CustomerWorkspace) -> None:
        self.workspace = workspace

    def get_connection(self, as_user=True):
        return SlackConnection(
            self.workspace.connection_token,
            as_user=as_user
        )

    def refresh_user_data(self):
        for platform_user in self.workspace.platformuser_set.all():
            connection = self.get_connection()
            action = Action(ActionType.GET_USER_INFO, {'user_id': platform_user.platform_id})
            response = connection.take_action(action)
            if response.get('ok'):
                profile = response['user']['profile']
                platform_user.profile_image = profile['image_72']
                platform_user.username = profile['display_name']
                platform_user.save()
            else:
                LOGGER.warning(
                    "Failed to update platform user data.",
                    extra={'platform_user_id': platform_user.id, 'error': response['error']}
                )

    def get_or_create_user_by_id(self, user_id: str) -> Optional[PlatformUser]:
        try:
            platform_user = PlatformUser.objects.get(
                platform_id=user_id,
                workspace_id=self.workspace.id
            )
        except PlatformUser.DoesNotExist:
            connection = self.get_connection()
            action = Action(ActionType.GET_USER_INFO, {'user_id': user_id})
            response = connection.take_action(action)
            if response.get('ok'):
                profile = response['user']['profile']
                platform_user = PlatformUser.objects.create(
                    platform_id=user_id,
                    workspace_id=self.workspace.id,
                    profile_image=profile['image_72'],
                    username=profile['display_name'],
                )
            else:
                LOGGER.error(
                    "Failed to update platform user data.",
                    extra={'platform_user_id': user_id, 'error': response['error']}
                )
                platform_user = None
        return platform_user


class MegatronChannelService:
    def __init__(self, channel: MegatronChannel) -> None:
        self.channel = channel

    def unarchive(self):
        connection = IntegrationService(self.channel.megatron_integration
                                        ).get_connection()
        response = connection.unarchive_channel(
            self.channel.platform_channel_id)
        if response['ok']:
            self.channel.last_message_sent = datetime.now(timezone.utc)
            self.channel.is_archived = False
            self.channel.save()
        return response

    def archive(self):
        connection = IntegrationService(self.channel.megatron_integration
                                        ).get_connection()
        response = connection.archive_channel(self.channel.platform_channel_id)
        if response['ok']:
            self.channel.is_archived = True
            self.channel.save()
        return response
