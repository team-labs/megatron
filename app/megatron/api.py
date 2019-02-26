import logging
import json
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.models import User

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from megatron.connections.actions import ActionType, Action
from megatron.statics import RequestData, NotificationChannels
from megatron.responses import MegatronResponse, OK_RESPONSE
from megatron.models import (
    MegatronChannel, MegatronIntegration,
    MegatronMessage, CustomerWorkspace, PlatformType
)
from megatron.services import IntegrationService
from megatron.bot_types import BotType
from megatron.errors import (raise_error, BroadcastError)


LOGGER = logging.getLogger(__name__)
BOT_TYPE = BotType.slack


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def incoming(request) -> MegatronResponse:
    msg = request.data['message']
    megatron_user = request.user
    integration = megatron_user.megatronintegration_set.first()
    team_interpreter = IntegrationService(integration).get_interpreter()
    channel = MegatronChannel.objects.filter(
        platform_user_id=msg['user']
    ).first()
    if not channel or channel.is_archived:
        return MegatronResponse({'ok': True, 'track': False}, 200)
    response = team_interpreter.incoming(msg, channel)
    if response.get('ok'):

        if response.get('watched_channel'):
            channel = MegatronChannel.objects.filter(
                platform_user_id=request.data['message']['user']
            ).first()
            MegatronMessage.objects.create(
                integration_msg_id=response['ts'],
                customer_msg_id=request.data['message']['ts'],
                megatron_channel=channel
            )

        return OK_RESPONSE
    return MegatronResponse(response.get('error'), 500)


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def outgoing(request) -> MegatronResponse:
    user_id = request.data['user']
    message = request.data['message']
    try:
        message['attachments'] = json.loads(message['attachments'])
    except TypeError:
        pass
    try:
        megatron_channel = MegatronChannel.objects.get(
            platform_user_id=user_id)
    except MegatronChannel.DoesNotExist:
        return MegatronResponse({'ok': True, 'track': False}, 200)
    if megatron_channel.is_archived:
        return MegatronResponse({'ok': True, 'track': False}, 200)

    megatron_integration = megatron_channel.megatron_integration
    customer_interpreter = IntegrationService(
        megatron_integration).get_interpreter()
    response = customer_interpreter.outgoing(message, megatron_channel)
    if response.get('ok'):
        if response.get('watched_channel'):
            megatron_msg = MegatronMessage(
                integration_msg_id=response['ts'],
                customer_msg_id=request.data['ts'],
                megatron_channel=megatron_channel
            )
            megatron_msg.save()

        return MegatronResponse({'ok': True, 'track': True}, 200)
    return MegatronResponse(
        {'error': response.get('error'), 'track': False}, 500)


def test(request):
    return MegatronResponse({'ok': True}, 200)


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def notify_user(request) -> MegatronResponse:
    msg = request.data['message']
    user_id = request.data['user_id']
    channel_id = request.data['channel_id']
    platform_type = request.data['platform_type']
    request_data = RequestData(
        channel_id=channel_id,
        user_id=user_id,
        response_url=""
    )
    platform_type = PlatformType[platform_type.capitalize()].value
    megatron_channel = MegatronChannel.objects.get(
        platform_channel_id=channel_id,
        workspace__platform_type=platform_type
    )
    connection = IntegrationService(
        megatron_channel.megatron_integration).get_connection(as_user=False)
    response = connection.ephemeral_message(
        request_data, msg)
    if response.get('ok'):
        return MegatronResponse({'ok': True, 'track': True}, 200)
    return MegatronResponse(
        {'error': response.get('error'), 'track': False}, 500)


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def broadcast(request) -> MegatronResponse:
    warnings: list = []
    required_params = ['text', 'broadcasts']
    for param in required_params:
        if param not in request.data:
            return MegatronResponse(
                {'error': f"Missing required param '{param}'."}, 400)
    text = request.data.get('text')
    broadcasts = request.data.get('broadcasts')

    try:
        message = json.loads(text)
    except ValueError:
        return raise_error(BroadcastError.malformed_broadcast,
                           status=status.HTTP_400_BAD_REQUEST)

    try:
        capture_feedback = request.data['capture_feedback']
    except KeyError:
        capture_feedback = False

    org_errors = {}
    for broadcast in broadcasts:
        bot_type = BotType[broadcast['platform_type']]
        org_platform_id = broadcast['org_id']
        user_ids = broadcast['user_ids']
        connection = bot_type.get_bot_connection_from_platform_id(org_platform_id)
        # deepcopy prevents direct mutation of original broadcast
        action = Action(ActionType.BROADCAST, {
            'broadcast':deepcopy(message),
            'user_ids': user_ids,
            'capture_feedback': capture_feedback,
        })
        response = connection.take_action(action)
        if not response.get('ok'):
            org_errors.update({org_platform_id: response.get('errors')})

    if org_errors:
        return MegatronResponse({'errors': org_errors}, 200)
    elif warnings:
        return MegatronResponse({'ok': True, 'warnings': warnings}, 200)
    else:
        return OK_RESPONSE


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def message(request, user_id) -> MegatronResponse:
    msg = request.data
    bot_type = BotType.slack

    try:
        user = User.objects.get(id=int(user_id))
    except User.DoesNotExist:
        return raise_error(BroadcastError.user_not_found,
                           status=status.HTTP_400_BAD_REQUEST)
    organization = user.profile.organization
    connection = bot_type.get_bot_connection(organization)
    response = connection.dm_user(user.slackuser.slack_id, msg)
    if response.get('ok'):
        return OK_RESPONSE
    return MegatronResponse(response.get('error'), response.get('status'))


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def edit(request):
    message = json.loads(request.body)
    # Warning! Currently the only way to identify msgs sent by Megatron
    try:
        footer_text = message['message']['attachments'][-1]['footer']
        if footer_text.startswith('sent by'):
            return OK_RESPONSE
    except KeyError:
        pass

    if message.get('user'):
        megatron_channel = MegatronChannel.objects.filter(
            platform_user_id=message['message']['user']
        ).first()
    elif message.get('channel'):
        megatron_channel = MegatronChannel.objects.filter(
            platform_channel_id=message['channel']
        ).first()
    else:
        return OK_RESPONSE
    if not megatron_channel:
        return OK_RESPONSE
    team_connection = IntegrationService(
        megatron_channel.megatron_integration
    ).get_connection(as_user=False)

    existing_message = MegatronMessage.objects.filter(
        customer_msg_id=message['previous_message']['ts'],
        megatron_channel=megatron_channel
    ).first()

    if not megatron_channel or not existing_message:
        return OK_RESPONSE

    new_message = {
        'text': message['message'].get('text', ''),
        'attachments': message['message'].get('attachments')
    }
    old_message = {
        'channel_id': megatron_channel.platform_channel_id,
        'ts': existing_message.integration_msg_id
    }
    params = {'new_message': new_message, 'old_message': old_message}
    update_action = Action(ActionType.UPDATE_MESSAGE, params)
    response = team_connection.take_action(update_action)

    existing_message.customer_msg_id = message['message']['ts']
    existing_message.integration_msg_id = response['ts']
    existing_message.save()

    return OK_RESPONSE


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def get_a_human(request):
    payload = json.loads(request.body)
    requesting_user = payload['requesting_user']
    workspace_id = payload['workspace_id']
    integration = MegatronIntegration.objects.get(megatron_user__id=request.user.id)
    team_connection = IntegrationService(integration).get_connection(as_user=False)

    # TODO: This should all be integration dependent
    channel = settings.NOTIFICATIONS_CHANNELS[
        NotificationChannels.customer_service]

    slack_name = requesting_user['with_team_domain']
    attach = {
        "color": '1f355e',
        "text": f"🆘 *{slack_name}* requested some help!",
        "callback_id": f"open",
        "actions": [
            {
                "name": "categorize",
                "text": "Open engagement channel",
                "type": "button",
                "value": f'{workspace_id}-{requesting_user["slack_id"]}'
            }
        ],
        "mrkdwn_in": ["text"]
    }
    msg = ({'text': ' ', 'attachments': [attach]})

    msg_action = Action(ActionType.POST_MESSAGE, {'channel': channel, 'message': msg})
    response = team_connection.take_action(msg_action)
    if response.get('ok'):
        return OK_RESPONSE
    return MegatronResponse(response.get('error'), response.get('status'))


@api_view(http_method_names=['POST'])
@permission_classes((IsAuthenticated, ))
def register_workspace(request) -> MegatronResponse:
    workspace_data = json.loads(request.body)
    try:
        platform_name = workspace_data['platform_type'].capitalize()
        platform_type_id = PlatformType[platform_name].value
    except AttributeError:
        return MegatronResponse("Unknown platform type.", 400)
    try:
        workspace, _ = CustomerWorkspace.objects.get_or_create(
            connection_token=workspace_data['connection_token'],
            platform_type=platform_type_id,
            defaults={
                'platform_id': workspace_data['platform_id'],
                'name': workspace_data['name'],
                'domain': workspace_data['domain']
            }
        )
    except:
        LOGGER.exception("Failed to create Workspace.")
        return MegatronResponse("Unknown error.", 500)
    return OK_RESPONSE
