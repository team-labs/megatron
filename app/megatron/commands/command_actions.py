import logging
from typing import Tuple
from datetime import datetime, timezone, timedelta

import requests
from celery import shared_task

from django.conf import settings
from django.contrib.auth.models import User

from megatron.interpreters.slack import formatting
from megatron.connections.actions import Action, ActionType
from megatron.models import (
    MegatronChannel, MegatronUser, MegatronMessage, PlatformUser,
    CustomerWorkspace
)
from megatron.services import (
    IntegrationService, WorkspaceService, MegatronChannelService)
from megatron.statics import RequestData


LOGGER = logging.getLogger(__name__)


@shared_task
def open_channel(megatron_user_id: int, serialized_request_data: dict, arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    platform_user_id = arguments['targeted_platform_id']
    integration = megatron_user.megatronintegration_set.first()
    connection = IntegrationService(integration).get_connection(as_user=False)

    # Ensure platform user exists
    if not PlatformUser.objects.filter(platform_id=platform_user_id).exists:
        user_info = connection._get_user_info(platform_user_id)
        workspace = CustomerWorkspace.objects.get(platform_id=user_info['team_id'])
        WorkspaceService(workspace).get_or_create_user_by_id(platform_user_id)

    new_msg = formatting.user_titled(platform_user_id, "Connecting....")
    response = connection.respond_to_url(request_data.response_url, new_msg)
    if not response.get('ok'):
        return response
    _update_channel_link.delay(megatron_user.id, platform_user_id,
                               request_data.response_url)
    return {'ok': True}


@shared_task
def close_channel(megatron_user_id: int, serialized_request_data: dict,
                  arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    targeted_slack_id = arguments['targeted_platform_id']
    try:
        megatron_channel = MegatronChannel.objects.get(
            platform_user_id=targeted_slack_id)
    except MegatronChannel.DoesNotExist:
        return {'ok': False, 'error': 'Channel not found'}

    response = _unpause_channel(megatron_user.id, request_data, arguments)
    if not response.get('ok'):
        return response

    response = MegatronChannelService(megatron_channel).archive()
    if not response.get('ok'):
        return response
    return {'ok': True}


@shared_task
def forward_message(channel: str, msg: dict, from_user: dict=None) -> dict:
    engagement_channel = _check_channel(channel)
    if not engagement_channel:
        return {'ok': False, 'error': f'Channel {channel} not found.'}
    platform_user_id = engagement_channel.platform_user_id

    workspace = engagement_channel.workspace
    connection = WorkspaceService(workspace).get_connection()
    if from_user:
        msg = connection.add_forward_footer(msg, from_user)
    response = connection.dm_user(platform_user_id, msg)

    engagement_channel.last_message_sent = datetime.now(timezone.utc)
    engagement_channel.save()

    megatron_msg, _ = MegatronMessage.objects.update_or_create(
        integration_msg_id=msg['ts'],
        megatron_channel=engagement_channel,
        defaults={
            'customer_msg_id': response['ts'],
        }
    )

    return {'ok': True, 'response': response}


@shared_task
def pause_channel(megatron_user_id: int, serialized_request_data: dict,
                  arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    platform_user = PlatformUser.objects.get(platform_id=arguments['targeted_platform_id'])
    response = _change_pause_state(
        megatron_user, platform_user, request_data, True)
    return response


@shared_task
def unpause_channel(megatron_user_id: int, serialized_request_data: dict,
                    arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    return _unpause_channel(megatron_user_id, request_data, arguments)


def _unpause_channel(megatron_user_id: int, request_data: RequestData,
                     arguments: dict) -> dict:
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    platform_user = PlatformUser.objects.get(platform_id=arguments['targeted_platform_id'])
    response = _change_pause_state(
        megatron_user, platform_user, request_data, False)
    return response


@shared_task
def clear_context(megatron_user_id: int, serialized_request_data: dict,
                  arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    platform_user_id = User.objects.get(id=arguments['platform_user_id'])
    command_url = getattr(megatron_user, 'command_url', None)
    if not command_url:
        return {
            'ok': False,
            'error': 'MegatronUser has not provided a command url.'
        }
    # TODO: Use the command that called this to standardize the 'command' param
    response = requests.post(
        megatron_user.command_url,
        json={
            'command': 'clear-context',
            'platform_user_id': platform_user_id,
            'megatron_verification_token': megatron_user.verification_token
        }
    )
    if not response.status_code == 200:
        return {'ok': False, 'error': response.content}

    # TODO: This is probably better suited to being part of the integration itself
    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(
        integration).get_connection(as_user=False)
    platform_username = PlatformUser.objects.get(platform_id=platform_user_id).username
    msg = {
        "text": f"Context cleared for *{platform_username}*."
    }
    integration_response = integration_connection.ephemeral_message(
        request_data, msg)

    if not integration_response.get('ok'):
        return {'ok': False, 'error': 'Failed to post confirmation to slack.'}

    return {'ok': True}


@shared_task
def do(megatron_user_id: int, serialized_request_data: dict,
       arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    try:
        channel = MegatronChannel.objects.get(
            platform_channel_id=request_data.channel_id)
    except MegatronChannel.DoesNotExist:
        return {'ok': False, 'error': 'Channel is invalid.'}
    workspace = channel.workspace
    connection = WorkspaceService(workspace).get_connection(
        as_user=False)
    response = connection.open_im(channel.platform_user_id)
    channel_id = response['channel']['id']
    msg = {
        'megatron_verification_token': settings.MEGATRON_VERIFICATION_TOKEN,
        'command': 'push_message',
        'message': {'text': arguments['arguments']},
        'channel_id': channel_id,
        'platform_user_id': channel.platform_user_id,
        'platform_channel_id': request_data.channel_id
    }
    try:
        requests.post(megatron_user.command_url, json=msg, timeout=10)
    except requests.Timeout:
        LOGGER.error("Timeout on megatron do.")
    return {'ok': True}


@shared_task
def _update_channel_link(megatron_user_id: int, platform_user_id: str, response_url: str):
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    integration = megatron_user.megatronintegration_set.first()
    connection = IntegrationService(integration).get_connection(as_user=False)
    platform_user = PlatformUser.objects.get(platform_id=platform_user_id)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    megatron_channel = MegatronChannel.objects.filter(
        platform_user_id=platform_user_id
    ).first()

    if not megatron_channel:
        username = platform_user.username + "_" + platform_user.workspace.domain
        response = connection.create_channel(
            f'{settings.CHANNEL_PREFIX}{username}')
        if not response:
            response = connection.respond_to_url(
                response_url, {"text": "Error creating channel."})
            if not response.get('ok'):
                LOGGER.error(f"Problem updating slack message: {response['error']}")
            return

        megatron_channel, created = _create_or_update_channel(
            megatron_user, response['channel'], platform_user)
        if created:
            _get_conversation_history(megatron_channel)

    elif megatron_channel.is_archived:
        MegatronChannelService(megatron_channel).unarchive()
        _get_conversation_history(megatron_channel)

    channel_link = _get_channel_link(megatron_user,
                                     megatron_channel.platform_channel_id)
    join_message = formatting.user_titled(
        platform_user_id, f"<{channel_link}|Go to slack conversation>")
    response = connection.respond_to_url(response_url, join_message)
    if not response.get('ok'):
        LOGGER.error(f"Problem updating slack message: {response['error']}")


def _check_channel(platform_channel_id: str):
    try:
        channel = MegatronChannel.objects.get(
            platform_channel_id=platform_channel_id)
    except MegatronChannel.DoesNotExist:
        channel = None
    return channel


def _get_channel_link(megatron_user: MegatronUser, channel_id: str):
    team_id = megatron_user.megatronintegration_set.first().platform_id
    link = f"slack://channel?team={team_id}&id={channel_id}"
    return link


def _create_or_update_channel(megatron_user, channel_data,
                              platform_user: PlatformUser) -> Tuple[MegatronChannel, bool]:
    workspace = platform_user.workspace
    channel, created = MegatronChannel.objects.get_or_create(
        megatron_user=megatron_user,
        workspace=workspace,
        platform_channel_id=channel_data['id'],
        defaults={
            'platform_user_id': platform_user.platform_id,
            'megatron_integration': (
                megatron_user.megatronintegration_set.first()
            ),
        }
    )
    return channel, created


def _get_conversation_history(channel: MegatronChannel):
    connection = WorkspaceService(channel.workspace).get_connection()
    response = connection.open_im(channel.platform_user_id)
    channel_id = response['channel']['id']
    prev_messages = connection.im_history(channel_id, 10)
    integration_interpreter = IntegrationService(
        channel.megatron_integration).get_interpreter()
    messages = prev_messages['messages']
    messages.sort(key=lambda message: message['ts'])
    previous_ts = None
    for message in messages:
        timestamp = datetime.fromtimestamp(int(message['ts'].split('.')[0]))
        formatted_timestamp = _format_slack_timestamp(timestamp, previous_ts)
        message['text'] = f"{formatted_timestamp}{message['text']}"
        previous_ts = timestamp

        if message.get('bot_id'):
            integration_interpreter.outgoing(message, channel)
        else:
            integration_interpreter.incoming(message, channel)
    return prev_messages


NEW_TIMESTAMP_BUFFER = 3


def _format_slack_timestamp(timestamp, previous_ts):
    if (
        previous_ts
        and timestamp - previous_ts <= timedelta(minutes=NEW_TIMESTAMP_BUFFER)
    ):
        return ""
    f_timestamp = timestamp.strftime('%b %d %I:%M %p')
    f_timestamp = f"*[{f_timestamp}]*\n"
    return f_timestamp


def _change_pause_state(megatron_user: MegatronUser, platform_user: User,
                        request_data: RequestData, pause=False
                        ) -> dict:
    workspace = platform_user.workspace
    if not getattr(megatron_user, 'command_url', None):
        return {'ok': False, 'error': 'No command url provided for workspace.'}

    customer_connection = WorkspaceService(
        workspace).get_connection(as_user=False)
    response = customer_connection.open_im(platform_user.platform_id)
    if not response['ok']:
        return {
            'ok': False,
            'error': 'Failed to open get im channel from '
            f"slack: {response['error']}"
        }
    channel_id = response['channel']['id']

    data = {
        'megatron_verification_token': settings.MEGATRON_VERIFICATION_TOKEN,
        'command': 'pause',
        'channel_id': channel_id,
        'platform_user_id': platform_user.platform_id,
        'team_id': workspace.platform_id,
        'paused': pause,
    }
    response = requests.post(megatron_user.command_url, json=data)
    # TODO: This response is 200 even on failure to find user
    if not response.status_code == 200:
        return {'ok': False, 'error': 'Failed to pause bot for user.'}

    megatron_channel = MegatronChannel.objects.get(
        workspace=workspace, platform_user_id=platform_user.platform_id)
    megatron_channel.is_paused = pause
    megatron_channel.save()

    # TODO: This is probably better suited to being part of the integration itself
    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(
        integration).get_connection(as_user=False)
    paused_word = 'paused' if pause else 'unpaused'
    msg = {
        "text": f"Bot *{paused_word}* for user: {platform_user}."
    }
    channel = request_data.channel_id
    message_action = Action(ActionType.POST_MESSAGE, {'channel': channel, 'message': msg})
    integration_connection.take_action(message_action)
    return {'ok': True}
