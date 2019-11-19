import logging
import requests
import json
import urllib.request

from celery import shared_task
from django.conf import settings

from megatron import models
from megatron import services
from megatron.connections import slack
from megatron.connections.actions import Action, ActionType

LOGGER = logging.getLogger(__name__)


class ZendeskConnection:

    default_zendesk_token = settings.ZENDESK_TOKEN
    default_zendesk_admin_email = settings.ZENDESK_ADMIN_EMAIL
    default_zendesk_bot_email = settings.ZENDESK_BOT_EMAIL
    default_zendesk_subdomain = settings.ZENDESK_SUBDOMAIN

    def __init__(
            self,
            token=default_zendesk_token,
            admin_email=default_zendesk_admin_email,
            bot_email=default_zendesk_bot_email,
            subdomain=default_zendesk_subdomain):
        self.token = token
        self.admin_email = admin_email
        self.bot_email = bot_email
        self.subdomain = subdomain

    def post_ticket(self, payload: dict):

        zendesk_url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"
        auth = (f"{self.admin_email}/token", self.token)
        headers = {'content-type': 'application/json'}

        response = requests.post(
            zendesk_url, json=payload, auth=auth, headers=headers, timeout=5
        )

        return response

    def put_comment(self, payload: dict, ticket_id: int):

        zendesk_url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}.json"
        auth = (f"{self.admin_email}/token", self.token)
        headers = {'content-type': 'application/json'}

        response = requests.put(
            zendesk_url, json=payload, auth=auth, headers=headers, timeout=5
        )

        return response

    def get_user_id_by_email(self, wanted_email: str, user: models.PlatformUser = None):

        zendesk_email_url = f"https://{self.subdomain}.zendesk.com/api/v2/users/search.json?query={wanted_email}"

        auth = (f"{self.admin_email}/token", self.token)
        headers = {'content-type': 'application/json'}

        response_email = requests.get(
            zendesk_email_url, auth=auth, headers=headers, timeout=5
        )
        response_email = response_email.json()

        if response_email["count"] == 0:
            zendesk_user_url = f"https://{self.subdomain}.zendesk.com/api/v2/users.json"
            payload = {
                "user":
                    {
                        "name": user.real_name,
                        "email": wanted_email
                     },
                }
            response_user = requests.post(
                zendesk_user_url, json=payload, auth=auth, headers=headers, timeout=5
            )
            print(response_user.json())
            return response_user.json()["user"]["id"]

        elif response_email["count"] == 1:
            return response_email["users"][0]["id"]
        else:
            LOGGER.error(
                "Multiple users found with the same email address.",
                extra={"email": wanted_email},
            )
        return

    def upload_attachment(self, attachment: dict, token_slack: str):

        connection = slack.SlackConnection(token_slack)
        file, ___ = connection.get_image(attachment)

        auth = (f"{self.admin_email}/token", self.token)
        headers = {'content-type': 'application/binary'}

        response = requests.post(
            f"https://{ZENDESK_CONNECTION.subdomain}.zendesk.com/api/v2/uploads.json?filename={attachment['name']}",
            headers=headers,
            auth=auth,
            data=file
        )

        return response


ZENDESK_CONNECTION = ZendeskConnection()


@shared_task(queue="megatron")
def incoming_message(channel_id: int, msg_data: dict):

    if ZENDESK_CONNECTION.token == "ignore":
        return

    workspace_platform_id = msg_data["team_id"]
    user_platform_id = msg_data["user"]
    workspace = models.CustomerWorkspace.objects.get(platform_id=workspace_platform_id)
    platform_user = services.WorkspaceService(workspace).get_or_create_user_by_id(
        user_platform_id
    )
    channel = models.MegatronChannel.objects.get(id=channel_id)

    if not platform_user:
        LOGGER.exception("Could not locate platform user for incoming Zendesk comment.")
        return
    assert platform_user is not None

    zendesk_ticket = models.ZendeskTickets.objects.filter(
        megatron_channel=channel,
        is_closed=False
    ).first()

    if not zendesk_ticket:
        zendesk_message = _translate_slack_msg_to_zendesk_msg(channel, platform_user, msg_data)

        response = ZENDESK_CONNECTION.post_ticket(zendesk_message)
        models.ZendeskTickets.objects.create(
            zendesk_id=response.json()["ticket"]["id"],
            megatron_channel=channel,
            is_closed=False
        )
    else:
        zendesk_id = zendesk_ticket.zendesk_id
        zendesk_message = _translate_slack_msg_to_zendesk_msg(channel, platform_user, msg_data, False)

        response = ZENDESK_CONNECTION.put_comment(zendesk_message, zendesk_id)

    if not response.ok and response.status_code != 200 and response.status_code != 201:
        _warn_zendesk_error(response)

    return


@shared_task(queue="megatron")
def outgoing_message(channel_id: int, user_platform_id: int, workspace_platform_id: int, msg_data: dict):

    # ignore the bot messages
    if ZENDESK_CONNECTION.token == "ignore" or ZENDESK_CONNECTION.bot_email == "ignore":
        return

    channel = models.MegatronChannel.objects.get(id=channel_id)
    workspace = models.CustomerWorkspace.objects.get(platform_id=workspace_platform_id)
    platform_user = services.WorkspaceService(workspace).get_or_create_user_by_id(
        str(user_platform_id)
    )

    if not platform_user:
        LOGGER.exception("Could not locate platform user for incoming Zendesk comment.")
        return
    assert platform_user is not None

    zendesk_ticket = models.ZendeskTickets.objects.filter(
        megatron_channel=channel,
        is_closed=False
    ).first()

    if not zendesk_ticket:
        zendesk_message = _translate_zendesk_bot_msg(channel, platform_user, msg_data)

        response = ZENDESK_CONNECTION.post_ticket(zendesk_message)
        models.ZendeskTickets.objects.create(
            zendesk_id=response.json()["ticket"]["id"],
            megatron_channel=channel,
            is_closed=False
        )
    else:
        zendesk_id = zendesk_ticket.zendesk_id
        zendesk_message = _translate_zendesk_bot_msg(channel, platform_user, msg_data, False)

        response = ZENDESK_CONNECTION.put_comment(zendesk_message, zendesk_id)

    if not response.ok and response.status_code != 200 and response.status_code != 201:
        _warn_zendesk_error(response)

    return


@shared_task(queue="megatron")
def team_member_message(channel_id: int, user_id: str, to_user_id: str, msg_data: dict):

    # TODO: SYNC PROBLEM WITH channel_unarchive AND channel_join
    if ZENDESK_CONNECTION.token == "ignore" or msg_data.get("subtype", "") == "channel_unarchive":
        return

    channel = models.MegatronChannel.objects.get(id=channel_id)
    from_user = models.PlatformUser.objects.get(
        platform_id=user_id,
        workspace__platform_type=models.PlatformType.Slack.value,
    )
    to_user = models.PlatformUser.objects.get(
        platform_id=to_user_id, workspace__platform_type=models.PlatformType.Slack.value
    )

    zendesk_ticket = models.ZendeskTickets.objects.filter(
        megatron_channel=channel,
        is_closed=False
    ).first()

    if not zendesk_ticket:
        zendesk_message = _translate_zendesk_slack_event(channel, from_user, to_user, msg_data)
        zendesk_message["ticket"]["comment"]["body"] = \
            f"~~The user {from_user.username} {zendesk_message['ticket']['comment']['body'].split(' ', 1)[1]}~~"

        response = ZENDESK_CONNECTION.post_ticket(zendesk_message)
        models.ZendeskTickets.objects.create(
            zendesk_id=response.json()["ticket"]["id"],
            megatron_channel=channel,
            is_closed=False
        )
    else:
        zendesk_id = zendesk_ticket.zendesk_id
        zendesk_message = _translate_zendesk_slack_event(channel, from_user, to_user, msg_data, False)

        if msg_data.get("subtype", "") == "channel_archive":
            zendesk_message["ticket"]["status"] = "solved"
            zendesk_message["ticket"]["comment"]["body"] = \
                f"~~The user {from_user.username} {zendesk_message['ticket']['comment']['body'].split(' ', 1)[1]}~~"

            zendesk_ticket = models.ZendeskTickets.objects.get(
                megatron_channel=channel,
                is_closed=False
            )
            zendesk_ticket.is_closed = True
            zendesk_ticket.save()
        response = ZENDESK_CONNECTION.put_comment(zendesk_message, zendesk_id)

    if not response.ok and response.status_code != 200 and response.status_code != 201:
        _warn_zendesk_error(response)

    return


def _translate_slack_msg_to_zendesk_msg(
        channel: models.MegatronChannel,
        platform_user: models.PlatformUser,
        slack_msg: dict,
        is_closed: bool = True
) -> dict:

    token_slack = channel.megatron_integration.connection_token
    user_info = _get_user_info_slack(platform_user, token_slack)

    user_id = ZENDESK_CONNECTION.get_user_id_by_email(
        user_info["user"]["profile"]["email"],
        platform_user
    )

    if is_closed:
        zendesk_message = {
            "ticket":
                {
                    "status": "open",
                    "tags": ["megatron", user_info["user"]["profile"]["email"]],
                    "subject": f"{user_info['user']['real_name']} -- {channel.name}",
                    "comment":
                        {
                            "body": slack_msg["text"]
                        },
                    "requester_id": user_id,
                    "submitter_id": user_id
                 },
        }
    else:
        zendesk_message = {
            "ticket":
                {
                    "comment":
                        {
                            "body": slack_msg["text"],
                            "author_id": user_id
                        }
                 },
        }

    if slack_msg.get("files"):
        zendesk_message["ticket"]["comment"]['uploads'] = _translate_slack_attachments(slack_msg["files"], token_slack)
        if slack_msg["text"] == "":
            zendesk_message["ticket"]["comment"]["body"] = "[FILE]"

    return zendesk_message


def _translate_zendesk_bot_msg(
        channel: models.MegatronChannel,
        platform_user: models.PlatformUser,
        slack_msg: dict,
        is_closed: bool = True
) -> dict:

    token_slack = channel.megatron_integration.connection_token
    user_info = _get_user_info_slack(platform_user, token_slack)

    bot_id = ZENDESK_CONNECTION.get_user_id_by_email(
        ZENDESK_CONNECTION.bot_email
    )

    if is_closed:

        user_id = ZENDESK_CONNECTION.get_user_id_by_email(
            user_info["user"]["profile"]["email"],
            platform_user
        )
        # buser_id = ZENDESK_CONNECTION.get_user_id_by_email("mamumarquezz@gmail.com", platform_user)
        zendesk_message = {
            "ticket":
                {
                    "status": "open",
                    "tags": ["megatron", user_info["user"]["profile"]["email"]],
                    "subject": f"{user_info['user']['real_name']} -- {channel.name}",
                    "comment":
                        {
                            "body": slack_msg["text"]
                        },
                    "requester_id": user_id,
                    "submitter_id": bot_id
                 },
        }
    else:
        zendesk_message = {
            "ticket":
                {
                    "comment":
                        {
                            "body": slack_msg["text"],
                            "author_id": bot_id
                        }
                 },
        }

    if slack_msg.get("files"):
        zendesk_message["ticket"]["comment"]['uploads'] = _translate_slack_attachments(slack_msg["files"], token_slack)
        if slack_msg["text"] == "":
            zendesk_message["ticket"]["comment"]["body"] = "[FILE]"

    return zendesk_message


def _translate_zendesk_slack_event(
        channel: models.MegatronChannel,
        from_user: models.PlatformUser,
        to_user: models.PlatformUser,
        slack_msg: dict,
        is_closed: bool = True
) -> dict:

    token_slack = channel.megatron_integration.connection_token
    from_user_info = _get_user_info_slack(from_user, token_slack)

    agent_id = ZENDESK_CONNECTION.get_user_id_by_email(
        from_user_info["user"]["profile"]["email"],
        from_user
    )
    # agent_id = ZENDESK_CONNECTION.get_user_id_by_email("gonzalo@teampay.co", from_user)

    if is_closed:
        to_user_info = _get_user_info_slack(to_user, token_slack)

        user_id = ZENDESK_CONNECTION.get_user_id_by_email(
            to_user_info["user"]["profile"]["email"],
            to_user
        )
        # user_id = ZENDESK_CONNECTION.get_user_id_by_email("mamumarquezz@gmail.com", to_user)

        zendesk_message = {
            "ticket":
                {
                    "status": "open",
                    "tags": ["megatron", to_user_info["user"]["profile"]["email"]],
                    "subject": f"{to_user_info['user']['real_name']} -- {channel.name}",
                    "comment":
                        {
                            "body": slack_msg["text"]
                        },
                    "requester_id": user_id,
                    "submitter_id": agent_id
                 },
        }
    else:
        zendesk_message = {
            "ticket":
                {
                    "comment":
                        {
                            "body": slack_msg["text"],
                            "author_id": agent_id
                        },
                 },
        }

    if slack_msg.get("files"):
        zendesk_message["ticket"]["comment"]['uploads'] = _translate_slack_attachments(slack_msg["files"], token_slack)
        if slack_msg["text"] == "":
            zendesk_message["ticket"]["comment"]["body"] = "[FILE]"

    return zendesk_message


def _translate_slack_attachments(slack_attachments: dict, token_slack: str) -> list:
    tokens = []
    for attachment in slack_attachments:
        response = ZENDESK_CONNECTION.upload_attachment(attachment, token_slack)
        tokens.append(response.json()["upload"]["token"])

    return tokens


def _get_user_info_slack(user: models.PlatformUser, token_slack: str):
    connection = slack.SlackConnection(token_slack)
    get_user_info_action = Action(ActionType.GET_USER_INFO, {"user_id": user.platform_id})
    user_info = connection.take_action(get_user_info_action)

    return user_info


def _warn_zendesk_error(response: requests.Response) -> None:
    LOGGER.error(
        "Failed to post megatron message to Zendesk.",
        extra={"error": response.status_code},
    )
