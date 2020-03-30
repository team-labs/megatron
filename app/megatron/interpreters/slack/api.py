import json
import logging
from json import JSONDecodeError

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.core.cache import cache
from django.db.utils import IntegrityError
from kombu.utils import json as kombu_json
from datetime import datetime

from megatron.authentication import validate_slack_token
from megatron.models import (
    MegatronChannel,
    MegatronUser,
    MegatronIntegration,
    CustomerWorkspace,
    MegatronMessage,
)
from megatron.connections.actions import Action, ActionType
from megatron.errors import catch_megatron_errors
from megatron.utils import remove_sensitive_data
from megatron.commands.commands import Command
from megatron.errors import MegatronException
from megatron.statics import RequestData
from megatron.services import WorkspaceService, IntegrationService
from megatron.interpreters.slack import formatting

BOTNAME = "Teampay"
LOGGER = logging.getLogger(__name__)


@catch_megatron_errors
def incoming(msg: dict, channel: MegatronChannel):

    workspace_service = WorkspaceService(channel.workspace)
    platform_user = workspace_service.get_or_create_user_by_id(msg["user"])
    if not platform_user:
        LOGGER.exception("Could not locate platform user for incoming message.")
        return

    workspace_connection = workspace_service.get_connection(as_user=False)
    integration_connection = IntegrationService(
        channel.megatron_integration
    ).get_connection(as_user=False)

    if msg.get("files", ""):
        msg = workspace_connection.build_img_attach(msg, platform_user)

    else:
        msg = {
            "username": platform_user.get_display_name(),
            "icon_url": platform_user.profile_image,
            "text": msg.get("text", None),
            "attachments": msg.get("attachments", None),
        }
    post_message_action = Action(
        ActionType.POST_MESSAGE,
        {"channel": channel.platform_channel_id, "message": msg},
    )
    response = integration_connection.take_action(post_message_action)
    response.update({"watched_channel": True})
    return response


@catch_megatron_errors
def outgoing(msg: dict, channel: MegatronChannel):

    cleaned_msg = remove_sensitive_data(msg)
    msg = {
        "username": BOTNAME,
        "icon_emoji": ":robot_face:",
        "text": cleaned_msg.get("text", None),
        "attachments": cleaned_msg.get("attachments", None),
    }
    integration_connection = IntegrationService(
        channel.megatron_integration
    ).get_connection(as_user=False)
    channel_id = channel.platform_channel_id
    post_message_action = Action(
        ActionType.POST_MESSAGE, {"channel": channel_id, "message": msg}
    )
    response = integration_connection.take_action(post_message_action)
    response.update({"watched_channel": True})
    return response


@csrf_exempt
@validate_slack_token
def slash_command(request):
    data = request.POST
    response_channel = data["channel_id"]
    response_user = data["user_id"]
    # Slash command response urls are associated with a "channel" rather than
    # a message. Responding to this url will generate new posts in a channel
    response_url = data["response_url"]
    request_data = RequestData(
        channel_id=response_channel, user_id=response_user, response_url=response_url
    )

    # TODO: There is only ever one megatron user, remove it
    megatron_user = MegatronUser.objects.first()

    args = data["text"].split(" ")
    command_str = args[0]
    command = Command.get_command(command_str)
    if not command:
        return JsonResponse({"text": "I don't recognize that command."})

    try:
        arguments = command.parse(args[1:], command, response_channel)
    except MegatronException as e:
        return JsonResponse(e.platform_message)
    command.action.delay(megatron_user.id, request_data, arguments)

    return HttpResponse(b"")


@csrf_exempt
def interactive_message(request):
    payload = json.loads(request.POST["payload"])
    megatron_user = MegatronIntegration.objects.get(
        platform_id=payload["team"]["id"]
    ).megatron_user
    callback_id = payload["callback_id"]
    action_type = payload["actions"][0]["type"]
    command_str = callback_id.split("|")[0]
    command = Command.get_command(command_str)
    response_channel = payload["channel"]["id"]
    response_url = payload["response_url"]
    response_user = payload["user"]["id"]

    request_data = RequestData(
        channel_id=response_channel, user_id=response_user, response_url=response_url
    )

    # TODO: Make all command.action calls async, at which point this is unneeded
    request_data = kombu_json.loads(kombu_json.dumps(request_data))

    if action_type == "select":
        workspace_id, platform_user_id = payload["actions"][0]["selected_options"][0][
            "value"
        ].split("-")
    elif action_type == "button":
        workspace_id, platform_user_id = payload["actions"][0]["value"].split("-")
    else:
        return JsonResponse({"text": "Received unknown action type"})

    try:
        workspace = CustomerWorkspace.objects.get(platform_id=workspace_id)
    except CustomerWorkspace.DoesNotExist:
        return JsonResponse({"text": "Customer Workspace not found"})
    platform_user = WorkspaceService(workspace).get_or_create_user_by_id(
        platform_user_id
    )

    if not platform_user:
        return JsonResponse({"text": "Platform User not found"})

    arguments = {
        "targeted_platform_user_id": platform_user.platform_id,
        "targeted_platform_workspace_id": workspace.platform_id,
    }

    command.action.delay(megatron_user.id, request_data, arguments)
    return HttpResponse(b"")


@csrf_exempt
def event(request):
    try:
        data = json.loads(request.body)
    except JSONDecodeError:
        return JsonResponse({"error": True, "error_message": "Invalid JSON"})
    if data.get("type") == "url_verification":
        return HttpResponse((data["challenge"]))
    if not data["type"] == "event_callback":
        return HttpResponse(b"")

    event = data["event"]
    if event["type"] != "message":
        return HttpResponse(b"")
    if event.get("bot_id"):
        return HttpResponse(b"")
    if event.get("message") and event["message"].get("bot_id"):
        return HttpResponse(b"")
    if event.get("message") and event["message"].get("subtype") == "bot_message":
        return HttpResponse(b"")

    subtype = event.get("subtype")
    channel_id = event.get("channel")
    user_id = event.get("user")
    if subtype == "message_changed":
        user_id = event["message"].get("user")

    try:
        tracked_channel = MegatronChannel.objects.get(platform_channel_id=channel_id)
    except MegatronChannel.DoesNotExist:
        return HttpResponse(b"")

    try:
        MegatronMessage.objects.create(
            megatron_channel=tracked_channel, integration_msg_id=event["event_ts"],
        )
    except IntegrityError:
        LOGGER.warning("Discarding duplicate event.", extra={"received_msg": data})
        return HttpResponse(b"")

    from_user = _get_slack_user_data(channel_id, user_id)
    if subtype:
        if subtype == "file_share":
            msg = _image_passthrough_message(event)
            Command.get_command("forward").action.delay(channel_id, msg, from_user)

        elif subtype == "message_changed":
            # Was changed by bot
            try:
                existing_message = MegatronMessage.objects.get(
                    integration_msg_id=event["previous_message"]["ts"],
                    megatron_channel=tracked_channel,
                )
            except MegatronMessage.DoesNotExist:
                return HttpResponse(b"")

            workspace_connection = WorkspaceService(
                tracked_channel.workspace
            ).get_connection(as_user=False)

            customer_channel_id = workspace_connection.open_im(
                tracked_channel.platform_user_id
            )["channel"]["id"]

            customer_ts = existing_message.customer_msg_id
            new_message = {
                "text": event["message"].get("text", " "),
                "attachments": event["message"].get("attachments", []),
            }
            new_message = workspace_connection.add_forward_footer(
                new_message, from_user
            )
            old_message = {
                "channel_id": customer_channel_id,
                "ts": customer_ts,
            }
            params = {"new_msg": new_message, "old_msg": old_message}

            update_action = Action(ActionType.UPDATE_MESSAGE, params)
            response = workspace_connection.take_action(update_action)

            existing_message.integration_msg_id = event["message"]["ts"]
            existing_message.customer_msg_id = response["ts"]
            existing_message.save()

    else:
        _check_and_send_paused_warning(tracked_channel, user_id)
        msg = {
            "text": event.get("text"),
            "attachments": event.get("attachments"),
            "ts": event.get("ts"),
        }
        Command.get_command("forward").action.delay(channel_id, msg, from_user)

    return HttpResponse(b"")


def _image_passthrough_message(event):
    tracked_channel = MegatronChannel.objects.filter(
        platform_channel_id=event["channel"]
    ).first()
    integration_service = IntegrationService(tracked_channel.megatron_integration)
    integration_connection = integration_service.get_connection(as_user=False)
    platform_agent = integration_service.get_or_create_user_by_id(event["user"])
    if not platform_agent:
        LOGGER.exception("Could not locate platform agent for sent message.")
        return

    msg = integration_connection.build_img_attach(event, platform_agent)
    return msg


def _get_slack_user_data(channel_id, slack_id):
    # TODO: Verify responses/that user exists
    incoming_channel = MegatronChannel.objects.get(platform_channel_id=channel_id)
    integration_connection = IntegrationService(
        incoming_channel.megatron_integration
    ).get_connection()
    action = Action(ActionType.GET_USER_INFO, {"user_id": slack_id})
    response = integration_connection.take_action(action)
    user_data = response["user"]
    from_user = {
        "user_name": user_data["profile"]["real_name"],
        "user_icon_url": user_data["profile"]["image_24"],
    }
    return from_user


TIME_TIL_NEXT_WARNING = 60
PAUSE_WARNING_PREFIX = "MEGATRON-PAUSE-WARNING-TIME|"


def _check_and_send_paused_warning(megatron_channel: MegatronChannel, user_id: str):
    if megatron_channel.is_paused:
        return

    last_warning = cache.get(PAUSE_WARNING_PREFIX + str(megatron_channel.id))
    if last_warning:
        last_warning = datetime.strptime(last_warning, "%d-%m-%Y:%H:%M:%S")
        minutes_elapsed = (datetime.now() - last_warning).total_seconds() / 60
        if minutes_elapsed < TIME_TIL_NEXT_WARNING:
            return

    workspace_id = megatron_channel.workspace.platform_id
    platform_user_id = megatron_channel.platform_user_id
    msg = formatting.get_unpaused_warning(workspace_id, platform_user_id)

    channel_id = megatron_channel.platform_channel_id
    integration_connection = IntegrationService(
        megatron_channel.megatron_integration
    ).get_connection(as_user=False)
    message_action = Action(
        ActionType.POST_MESSAGE, {"channel": channel_id, "message": msg}
    )
    integration_connection.take_action(message_action)

    last_warning = datetime.now().strftime("%d-%m-%Y:%H:%M:%S")
    cache.set(PAUSE_WARNING_PREFIX + str(megatron_channel.id), last_warning)
