import logging
import re
from typing import Tuple
from datetime import datetime, timezone, timedelta

import requests
from celery import shared_task

from django.conf import settings

from megatron.interpreters.slack import formatting
from megatron.models import (
    MegatronChannel,
    MegatronUser,
    MegatronMessage,
    PlatformUser,
    CustomerWorkspace,
)
from megatron.services import (
    IntegrationService,
    WorkspaceService,
    MegatronChannelService,
)
from megatron.statics import RequestData


LOGGER = logging.getLogger(__name__)


@shared_task
def open_channel(
    megatron_user_id: int, serialized_request_data: dict, arguments: dict
) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    platform_workspace_id = arguments["targeted_platform_workspace_id"]
    platform_user_id = arguments["targeted_platform_user_id"]

    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )

    # Ensure platform user and workspace exists
    try:
        workspace = CustomerWorkspace.objects.get(platform_id=platform_workspace_id)
    except CustomerWorkspace.DoesNotExist:
        new_msg = formatting.error_ephemeral(
            "Customer Workspace not found for user:",
            {"user_id": platform_user_id, "workspace_id": platform_workspace_id,},
        )
        integration_connection.respond_to_url(request_data.response_url, new_msg)
        return {"ok": False, "error": "Customer Workspace not found"}
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        platform_user_id
    )
    if not platform_user:
        return {
            "ok": False,
            "error": "Could not locate platform user for incoming action",
        }

    new_msg = formatting.user_titled(platform_user, "Connecting...")
    response = integration_connection.respond_to_url(request_data.response_url, new_msg)
    if not response.get("ok"):
        return response
    _update_channel_link(megatron_user.id, platform_user, request_data.response_url)
    return response


@shared_task
def close_channel(
    megatron_user_id: int, serialized_request_data: dict, arguments: dict
) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    workspace = CustomerWorkspace.objects.get(
        platform_id=arguments["targeted_platform_workspace_id"]
    )
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        arguments["targeted_platform_user_id"]
    )
    if not platform_user:
        return {
            "ok": False,
            "error": "Could not locate platform user for incoming action",
        }

    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )

    workspace = platform_user.workspace
    megatron_channel = MegatronChannel.objects.get(
        workspace=workspace, platform_user_id=platform_user.platform_id
    )
    if megatron_channel.is_paused:
        response = _change_pause_state(
            megatron_user, platform_user, request_data, False
        )
        if not response.get("ok"):
            return response

    try:
        megatron_channel = MegatronChannel.objects.get(
            platform_user_id=platform_user.platform_id
        )
    except MegatronChannel.DoesNotExist:
        new_msg = formatting.error_ephemeral(
            "Channel not found for user.",
            {"user": platform_user.username, "channel_id": platform_user.platform_id},
        )
        integration_connection.respond_to_url(request_data.response_url, new_msg)
        return {"ok": False, "error": "Channel not found"}

    response = MegatronChannelService(megatron_channel).archive()

    if response.get("ok"):
        new_msg = formatting.user_titled(
            platform_user, "Got it! The channel was closed."
        )
    else:
        new_msg = formatting.user_titled(
            platform_user, "Couldn't find an open channel."
        )

    response = integration_connection.respond_to_url(request_data.response_url, new_msg)
    return response


# TODO Clear this function and adequate it to sync execution, return of ephemeral messages and call parameter from
#  the commands
@shared_task
def forward_message(channel: str, msg: dict, from_user: dict = None) -> dict:
    engagement_channel = _check_channel(channel)
    if not engagement_channel:
        return {"ok": False, "error": f"Channel {channel} not found."}
    platform_user_id = engagement_channel.platform_user_id

    workspace = engagement_channel.workspace
    connection = WorkspaceService(workspace).get_connection()
    if from_user:
        msg = connection.add_forward_footer(msg, from_user)
    response = connection.dm_user(platform_user_id, msg)

    engagement_channel.last_message_sent = datetime.now(timezone.utc)
    engagement_channel.save()

    megatron_msg, _ = MegatronMessage.objects.exclude(
        integration_msg_id__isnull=True
    ).update_or_create(
        integration_msg_id=msg.get("ts"),
        megatron_channel=engagement_channel,
        defaults={"customer_msg_id": response["ts"]},
    )

    return {"ok": True, "response": response}


@shared_task
def pause_channel(
    megatron_user_id: int, serialized_request_data: dict, arguments: dict
) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    workspace = CustomerWorkspace.objects.get(
        platform_id=arguments["targeted_platform_workspace_id"]
    )
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        arguments["targeted_platform_user_id"]
    )
    if not platform_user:
        return {
            "ok": False,
            "error": "Could not locate platform user for incoming action",
        }

    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )

    response = _change_pause_state(megatron_user, platform_user, request_data, True)

    if response.get("ok"):
        new_msg = formatting.get_pause_warning(
            platform_user.workspace.platform_id, platform_user.platform_id
        )
    else:
        new_msg = {"text": response.get("error")}

    response = integration_connection.respond_to_url(request_data.response_url, new_msg)
    return response


@shared_task
def unpause_channel(
    megatron_user_id: int, serialized_request_data: dict, arguments: dict
) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    workspace = CustomerWorkspace.objects.get(
        platform_id=arguments["targeted_platform_workspace_id"]
    )
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        arguments["targeted_platform_user_id"]
    )
    if not platform_user:
        return {
            "ok": False,
            "error": "Could not locate platform user for incoming action",
        }

    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )

    response = _change_pause_state(megatron_user, platform_user, request_data, False)

    if response.get("ok"):
        new_msg = formatting.get_unpaused_warning(
            platform_user.workspace.platform_id, platform_user.platform_id
        )
    else:
        new_msg = {"text": response.get("error")}

    response = integration_connection.respond_to_url(request_data.response_url, new_msg)
    return response


@shared_task
def clear_context(
    megatron_user_id: int, serialized_request_data: dict, arguments: dict
) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    workspace = CustomerWorkspace.objects.get(
        platform_id=arguments["targeted_platform_workspace_id"]
    )
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        arguments["targeted_platform_user_id"]
    )
    if not platform_user:
        return {
            "ok": False,
            "error": "Could not locate platform user for incoming action",
        }

    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )

    command_url = getattr(megatron_user, "command_url", None)
    if not command_url:
        new_msg = formatting.error_ephemeral(
            "MegatronUser has not provided a command url.",
            {"organization": megatron_user.organization_name},
        )
        integration_connection.respond_to_url(request_data.response_url, new_msg)
        return {"ok": False, "error": "MegatronUser has not provided a command url."}

    response_request = requests.post(
        megatron_user.command_url,
        json={
            "command": "clear-context",
            "platform_user_id": platform_user.platform_id,
            "megatron_verification_token": settings.MEGATRON_VERIFICATION_TOKEN,
        },
    )
    if not response_request.status_code == 200:
        new_msg = formatting.error_ephemeral(f"Request unsuccessful")
        integration_connection.respond_to_url(request_data.response_url, new_msg)
        return {"ok": False, "error": response_request.content}

    new_msg = {"text": f"Context cleared for *{platform_user.username}*."}
    response = integration_connection.respond_to_url(request_data.response_url, new_msg)

    return response


# TODO Clear this function and adequate it to both sync execution and return of ephemeral messages
@shared_task
def do(megatron_user_id: int, serialized_request_data: dict, arguments: dict) -> dict:
    request_data = RequestData(**serialized_request_data)
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    try:
        channel = MegatronChannel.objects.get(
            platform_channel_id=request_data.channel_id
        )
    except MegatronChannel.DoesNotExist:
        return {"ok": False, "error": "Channel is invalid."}
    workspace = channel.workspace
    connection = WorkspaceService(workspace).get_connection(as_user=False)
    response = connection.open_im(channel.platform_user_id)
    channel_id = response["channel"]["id"]
    msg = {
        "megatron_verification_token": settings.MEGATRON_VERIFICATION_TOKEN,
        "command": "push_message",
        "message": {"text": arguments["arguments"]},
        "channel_id": channel_id,
        "platform_user_id": channel.platform_user_id,
        "platform_channel_id": request_data.channel_id,
    }
    try:
        requests.post(megatron_user.command_url, json=msg, timeout=10)
    except requests.Timeout:
        LOGGER.error("Timeout on megatron do.")
    return {"ok": True}


def _update_channel_link(
    megatron_user_id: int, platform_user: PlatformUser, response_url: str
):
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)
    integration = megatron_user.megatronintegration_set.first()
    integration_connection = IntegrationService(integration).get_connection(
        as_user=False
    )
    megatron_user = MegatronUser.objects.get(id=megatron_user_id)

    megatron_channel = MegatronChannel.objects.filter(
        platform_user_id=platform_user.platform_id
    ).first()

    if not megatron_channel:
        username = platform_user.username + "_" + platform_user.workspace.domain
        username = re.sub(r"[^\w-]", "", username.lower())
        response = integration_connection.create_channel(
            f"{settings.CHANNEL_PREFIX}{username}"
        )
        if not response:
            integration_connection.respond_to_url(
                response_url, {"text": "Error creating channel."}
            )
            return

        megatron_channel, created = _create_or_update_channel(
            megatron_user, response["channel"], platform_user, username
        )
        if created:
            _get_conversation_history(megatron_channel)

    elif megatron_channel.is_archived:
        integration_connection._refresh_access_token(platform_user.platform_id)
        MegatronChannelService(megatron_channel).unarchive()
        _get_conversation_history(megatron_channel)

    channel_link = _get_channel_link(
        megatron_user, megatron_channel.platform_channel_id
    )
    join_message = formatting.user_titled(
        platform_user, f"<{channel_link}|Go to slack conversation>"
    )
    integration_connection.respond_to_url(response_url, join_message)


def _check_channel(platform_channel_id: str):
    try:
        channel = MegatronChannel.objects.get(platform_channel_id=platform_channel_id)
    except MegatronChannel.DoesNotExist:
        channel = None
    return channel


def _get_channel_link(megatron_user: MegatronUser, channel_id: str):
    team_id = megatron_user.megatronintegration_set.first().platform_id
    link = f"slack://channel?team={team_id}&id={channel_id}"
    return link


def _create_or_update_channel(
    megatron_user, channel_data, platform_user: PlatformUser, username: str
) -> Tuple[MegatronChannel, bool]:
    workspace = platform_user.workspace
    channel, created = MegatronChannel.objects.update_or_create(
        megatron_user=megatron_user,
        workspace=workspace,
        platform_channel_id=channel_data["id"],
        defaults={
            "platform_user_id": platform_user.platform_id,
            "megatron_integration": (megatron_user.megatronintegration_set.first()),
            "name": f"{settings.CHANNEL_PREFIX}{username}",
        },
    )
    return channel, created


def _get_conversation_history(channel: MegatronChannel):
    workspace_connection = WorkspaceService(channel.workspace).get_connection()
    response = workspace_connection.open_im(channel.platform_user_id)
    channel_id = response["channel"]["id"]
    prev_messages = workspace_connection.im_history(channel_id, 10)
    integration_interpreter = IntegrationService(
        channel.megatron_integration
    ).get_interpreter()
    messages = prev_messages["messages"]
    messages.sort(key=lambda message: message["ts"])
    previous_ts = None
    for message in messages:
        timestamp = datetime.fromtimestamp(int(message["ts"].split(".")[0]))
        formatted_timestamp = _format_slack_timestamp(timestamp, previous_ts)
        message["text"] = f"{formatted_timestamp}{message['text']}"
        previous_ts = timestamp

        if message.get("bot_id"):
            integration_interpreter.outgoing(message, channel)
        else:
            integration_interpreter.incoming(message, channel)
    return prev_messages


NEW_TIMESTAMP_BUFFER = 3


def _format_slack_timestamp(timestamp, previous_ts):
    if previous_ts and timestamp - previous_ts <= timedelta(
        minutes=NEW_TIMESTAMP_BUFFER
    ):
        return ""
    f_timestamp = timestamp.strftime("%b %d %I:%M %p")
    f_timestamp = f"*[{f_timestamp}]*\n"
    return f_timestamp


def _change_pause_state(
    megatron_user: MegatronUser,
    platform_user: PlatformUser,
    request_data: RequestData,
    pause_state=False,
) -> dict:
    workspace = platform_user.workspace
    if not getattr(megatron_user, "command_url", None):
        return {"ok": False, "error": "No command url provided for workspace."}

    workspace_connection = WorkspaceService(workspace).get_connection(as_user=False)
    response = workspace_connection.open_im(platform_user.platform_id)
    if not response["ok"]:
        return {
            "ok": False,
            "error": "Failed to open get im channel from "
            f"slack: {response['error']}",
        }
    channel_id = response["channel"]["id"]

    data = {
        "megatron_verification_token": settings.MEGATRON_VERIFICATION_TOKEN,
        "command": "pause",
        "channel_id": channel_id,
        "platform_user_id": platform_user.platform_id,
        "team_id": workspace.platform_id,
        "paused": pause_state,
    }
    response = requests.post(megatron_user.command_url, json=data)
    # TODO: This response is 200 even on failure to find user
    if not response.status_code == 200:
        return {"ok": False, "error": "Failed to pause bot for user."}

    megatron_channel = MegatronChannel.objects.get(
        workspace=workspace, platform_user_id=platform_user.platform_id
    )
    megatron_channel.is_paused = pause_state
    megatron_channel.save()

    # TODO: This is probably better suited to being part of the integration itself
    integration_service = IntegrationService(megatron_channel.megatron_integration)
    integration_connection = integration_service.get_connection(as_user=False)

    paused_word = "paused" if pause_state else "unpaused"
    msg = {"text": f"Bot *{paused_word}* for user: {platform_user.username}."}
    integration_connection.ephemeral_message(request_data, msg)

    platform_agent = IntegrationService(
        megatron_channel.megatron_integration
    ).get_or_create_user_by_id(request_data.user_id)

    if not platform_agent:
        attach = {
            "text": "",
            "footer": f"executed by Teampay",
        }
    else:
        attach = {
            "text": "",
            "footer": f"executed by {platform_agent.username} from Teampay",
            "footer_icon": f"{platform_agent.profile_image}",
        }

    paused_phrase = (
        "Hey, there! I've been paused so a support agent can talk with you. I'll let you know when I'm back online"
        if pause_state
        else "Hey, there! I've been unpaused and I'm back online to help you with everything I can. "
    )
    user_msg = {
        "text": paused_phrase,
        "attachments": [attach],
    }
    response = forward_message(megatron_channel.platform_channel_id, user_msg)
    return response
