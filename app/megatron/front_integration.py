import logging
import requests
from celery import shared_task
from django.conf import settings

from megatron import models
from megatron import services

LOGGER = logging.getLogger(__name__)


class FrontConnection:
    front_incoming_url = (
        f"https://api2.frontapp.com/channels/{settings.FRONT_CHANNEL}/incoming_messages"
    )
    default_front_token = settings.FRONT_TOKEN

    def __init__(self, token=default_front_token):
        self.token = token

    def post_message(self, message: dict):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(
            self.front_incoming_url, headers=headers, json=message, timeout=5
        )
        return response


FRONT_CONNECTION = FrontConnection()


@shared_task(queue="megatron")
def incoming_message(msg_data: dict):
    if FRONT_CONNECTION.token == "ignore":
        return

    workspace_platform_id = msg_data["team_id"]
    user_platform_id = msg_data["user"]
    workspace = models.CustomerWorkspace.objects.get(platform_id=workspace_platform_id)
    platform_user = services.WorkspaceService(workspace).get_or_create_user_by_id(
        user_platform_id
    )

    if not platform_user:
        LOGGER.exception("Could not locate platform user for incoming Front message.")
        return
    assert platform_user is not None

    front_message = _translate_slack_msg_to_front_msg(platform_user, msg_data)
    response = FRONT_CONNECTION.post_message(front_message)
    if not response.ok and response.status_code != 202:
        _warn_front_error(response)


@shared_task(queue="megatron")
def outgoing_message(user_platform_id: int, workspace_platform_id: int, msg_data: dict):
    if FRONT_CONNECTION.token == "ignore":
        return

    workspace = models.CustomerWorkspace.objects.get(platform_id=workspace_platform_id)
    platform_user = services.WorkspaceService(workspace).get_or_create_user_by_id(
        str(user_platform_id)
    )

    if not platform_user:
        LOGGER.exception("Could not locate platform user for incoming Front message.")
        return
    assert platform_user is not None

    front_message = _translate_front_bot_msg(platform_user, msg_data)
    response = FRONT_CONNECTION.post_message(front_message)
    if not response.ok and response.status_code != 202:
        _warn_front_error(response)


@shared_task(queue="megatron")
def team_member_message(user_id: str, to_user_id: str, msg_data: dict):
    if FRONT_CONNECTION.token == "ignore":
        return

    front_message = _translate_front_slack_event(user_id, to_user_id, msg_data)
    FRONT_CONNECTION.post_message(front_message)


def _translate_slack_msg_to_front_msg(
    platform_user: models.PlatformUser, slack_msg: dict
) -> dict:
    front_message = {
        "sender": {"name": str(platform_user), "handle": str(platform_user)},
        "subject": str(platform_user),
        "body": slack_msg["text"],
        "attachments": [],
        "metadata": {"thread_ref": str(platform_user.id)},
    }
    if slack_msg.get("attachments"):
        attachment_text = _translate_slack_attachments(slack_msg["attachments"])
        front_message["text"] += attachment_text
    return front_message


def _translate_front_bot_msg(
    platform_user: models.PlatformUser, slack_msg: dict
) -> dict:
    front_message = {
        "sender": {"name": "Teampay Bot", "handle": "teampay_bot"},
        "subject": str(platform_user),
        "body": slack_msg["text"],
        "attachments": [],
        "metadata": {"thread_ref": str(platform_user.id)},
    }
    if slack_msg.get("attachments"):
        attachment_text = _translate_slack_attachments(slack_msg["attachments"])
        front_message["body"] += attachment_text
    return front_message


def _translate_front_slack_event(
    from_user_id: str, to_user_id: str, slack_msg: dict
) -> dict:
    from_user = models.PlatformUser.objects.get(
        platform_id=from_user_id,
        workspace__platform_type=models.PlatformType.Slack.value,
    )
    to_user = models.PlatformUser.objects.get(
        platform_id=to_user_id, workspace__platform_type=models.PlatformType.Slack.value
    )
    front_message = {
        "sender": {
            "name": f"(Teampay) {from_user}",
            "handle": f"(Teampay) {from_user}",
        },
        "subject": str(to_user),
        "body": slack_msg["text"],
        "attachments": [],
        "metadata": {"thread_ref": str(to_user.id)},
    }
    if slack_msg.get("files"):
        front_message["body"] += "( Screenshot )"
    if slack_msg.get("attachments"):
        attachment_text = _translate_slack_attachments(slack_msg["attachments"])
        front_message["body"] += attachment_text
    return front_message


def _translate_slack_attachments(slack_attachments: dict) -> str:
    attachment_text = ""
    for attachment in slack_attachments:
        attachment_text += f"\n{attachment.get('text', '')}"

        fields = attachment.get("fields", [])
        if fields:
            attachment_text += "\n"
        for field in fields:
            attachment_text += f"\n{field['title']}: {field['value']}"

        actions = attachment.get("actions", [])
        if actions:
            attachment_text += "\n"
        for action in actions:
            if action["type"] == "button":
                attachment_text += f"[ {action.get('text', '')} ]  "
            elif action["type"] == "select":
                attachment_text += f"[ v {action.get('text', '')} v ]  "
    return attachment_text


def _warn_front_error(response: requests.Response) -> None:
    resp_message = response.json()
    error = resp_message["_error"]
    LOGGER.error(
        "Failed to post megatron message to front.",
        extra={"error": error["message"], "details": error.get("details", "")},
    )
