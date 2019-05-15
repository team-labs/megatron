import logging
import json
import os
import requests
from typing import Tuple, List, Optional
from simplejson.scanner import JSONDecodeError

from django.contrib.auth.models import User

from megatron.connections.actions import ActionType, Action
from .bot_connection import BotConnection
from megatron.models import PlatformUser, CustomerWorkspace, MegatronUser
from megatron.errors import (
    catch_megatron_errors, MegatronException)
from megatron.connections.safe_requests import SafeRequest
from megatron import aws


LOGGER = logging.getLogger(__name__)
OPEN_IM_URL = "https://slack.com/api/im.open"
IM_HISTORY_URL = "https://slack.com/api/im.history"

CHAT_POST_URL = "https://slack.com/api/chat.postMessage"
CHAT_POST_EPHEMERAL_URL = "https://slack.com/api/chat.postEphemeral"
CHAT_UPDATE_URL = "https://slack.com/api/chat.update"

JOIN_CHANNEL_URL = "https://slack.com/api/channels.join"
CHANNELS_LIST_URL = "https://slack.com/api/channels.list"

GET_USER_INFO_URL = "https://slack.com/api/users.info"

CONVERSATION_CREATE_URL = "https://slack.com/api/conversations.create"
CONVERSATION_JOIN_URL = "https://slack.com/api/conversations.join"
CONVERSATION_ARCHIVE_URL = "https://slack.com/api/conversations.archive"
CONVERSATION_UNARCHIVE_URL = "https://slack.com/api/conversations.unarchive"

BOTNAME = "Teampay"


def response_verification(response):
    if response.text == 'ok':
        return True
    try:
        json_data = response.json()
        if not json_data.get('ok') or json_data.get('error'):
            return False
    except JSONDecodeError:
        pass
    return True


def get_response_data(response):
    if response.text == "ok":
        response_data = {}
    try:
        response_data = response.json()
    except ValueError:
        response_data = {'error': 'Could not decode response body.'}
    return response_data


safe_requests = SafeRequest(response_verification, get_response_data)


class SlackConnection(BotConnection):
    def __init__(self, token, as_user=True):
        self.token = token
        self.as_user = as_user

    def take_action(self, action: Action):
        if action.type == ActionType.POST_MESSAGE:
            response = self._post_message(**action.params)
        elif action.type == ActionType.POST_EPHEMERAL_MESSAGE:
            response = self._post_ephemeral_message(**action.params)
        elif action.type == ActionType.UPDATE_MESSAGE:
            response = self._update_msg(**action.params)
        elif action.type == ActionType.GET_USER_INFO:
            response = self._get_user_info(**action.params)
        elif action.type == ActionType.BROADCAST:
            response = self._broadcast(**action.params)
        return response

    def _broadcast(self, broadcast: dict, user_ids: List[str],
                  capture_feedback: bool):
        if capture_feedback and broadcast.get('attachments'):
            broadcast['attachments'].append(self._build_feedback_attach())
        elif capture_feedback:
            broadcast['attachments'] = [self._build_feedback_attach()]

        errors = []
        for slack_id in user_ids:
            try:
                response = self.open_im(slack_id)
                channel_id = response['channel']['id']
            except MegatronException as ex:
                error = {slack_id: str(ex)}
                errors.append(error)
                continue

            try:
                self._post_to_channel(channel_id, broadcast)
            except MegatronException as ex:
                error = {slack_id: str(ex)}
                errors.append(error)
                continue
        if errors:
            return {'ok': False, 'errors': errors}
        else:
            return {'ok': True}

    @catch_megatron_errors
    def _post_message(self, message: dict, channel: str) -> dict:
        response = self._post_to_channel(channel, message)
        return response.json()


    @catch_megatron_errors
    def _get_user_info(self, user_id: str)-> dict:
        # TODO: IMPORTANT `safe_requests.get` seems to be borked
        response = requests.get(
            GET_USER_INFO_URL, {'token': self.token, 'user': user_id})

        response_json = response.json()
        if not response_json.get('ok', False):
            if response_json.get('error') == 'invalid_auth':
                self._refresh_access_token(user_id)
                response = requests.get(GET_USER_INFO_URL, {'token': self.token, 'user': user_id})

        return response.json()

    @catch_megatron_errors
    def respond_to_url(self, response_url: str, msg: dict) -> dict:
        response = self._post_to_response_url(response_url, msg)
        # When responding to slash commands, slack returns a text response
        # This mimics the dict that would be returned by response.json()
        try:
            response_data = response.json()
        except JSONDecodeError:
            if response.text == 'ok':
                response_data = {'ok': True}
            else:
                response_data = {'ok': False}
        return response_data

    @catch_megatron_errors
    def ephemeral_message(self, request_data, msg: dict) -> dict:
        response = self._post_ephemeral_message(request_data, msg)
        return response.json()

    @catch_megatron_errors
    def dm_user(self, slack_id: str, msg: dict) -> dict:
        open_response = self.open_im(slack_id)

        channel = open_response['channel']['id']
        response = self._post_to_channel(channel, msg)

        return response.json()

    def open_im(self, slack_user_id: str):
        open_im_data = {'token': self.token, 'user': slack_user_id}
        open_response = safe_requests.post(OPEN_IM_URL, open_im_data)
        open_response_data = open_response.json()
        if not open_response_data['ok']:
            raise MegatronException(
                "Could not open DM channel with user: {}.  Error: {}"
                .format(slack_user_id, open_response_data['error'])
            )
        return open_response_data

    @catch_megatron_errors
    def im_history(self, channel_id: str, count: int):
        im_history_data = {
            'token': self.token,
            'channel': channel_id,
            'count': count,
        }
        response = safe_requests.post(IM_HISTORY_URL, im_history_data)
        response_data = response.json()
        if not response_data['ok']:
            raise MegatronException(
                (
                    "Could not retrieve history for DM channel: {}. "
                    "Error: {}"
                ).format(channel_id, response_data['error'])
            )
        return response_data

    @catch_megatron_errors
    def create_channel(self, channel_name: str) -> Optional[dict]:
        data = {
            'token': self.token,
            'name': channel_name[:21],
        }
        response = safe_requests.post(CONVERSATION_CREATE_URL, data)
        response_data = response.json()
        if not response_data['ok']:
            LOGGER.error("Unable to create channel.",
                         extra={'response': response_data})
            return None
        return response_data

    @catch_megatron_errors
    def archive_channel(self, channel_id: str) -> dict:
        data = {
            'token': self.token,
            'channel': channel_id
        }
        response = safe_requests.post(CONVERSATION_ARCHIVE_URL, data)
        return response.json()

    @catch_megatron_errors
    def unarchive_channel(self, channel_id: str) -> dict:
        data = {
            'token': self.token,
            'channel': channel_id
        }
        response = safe_requests.post(CONVERSATION_UNARCHIVE_URL, data)
        return response.json()

    @catch_megatron_errors
    def _update_msg(self, new_msg: dict, old_msg: dict) -> dict:
        new_msg['attachments'] = json.dumps(new_msg.get('attachments', []))
        headers = {'Authorization': f'Bearer {self.token}'}
        data = {
            'text': ' ',
            'channel': old_msg['channel_id'],
            'ts': old_msg['ts'],
            'attachments': [],
            'as_user': self.as_user
        }
        data.update(new_msg)
        response = safe_requests.post(CHAT_UPDATE_URL, headers=headers, json=data)
        return json.loads(response.text)

    @catch_megatron_errors
    def get_image(self, file_data: dict) -> Optional[Tuple[bytes, str]]:
        url = file_data['url_private']
        response = safe_requests.get(url,
                                     headers={'Authorization': f'Bearer {self.token}'})
        if response.status_code == 200:
            image = response.content
        else:
            LOGGER.error(f'Error downloading image from Slack:'
                         f'{response.text}')
            return None

        _, extension = os.path.splitext(url)

        return image, extension

    def get_channel_by_name(self, channel_name) -> Optional['dict']:
        selected_channel = None
        data = {
                'token': self.token,
                'exclude_members': True
            }
        response = safe_requests.post(CHANNELS_LIST_URL, data)
        response_data = response.json()
        if not response_data['ok']:
            return None
        for channel in response_data['channels']:
            formatted_channel_name = channel_name.replace('@', '_')
            if formatted_channel_name.startswith(channel['name']):
                selected_channel = channel
                return selected_channel
        return None

    def _post_to_response_url(self, response_url: str, msg: dict):
        post_msg_data = {
            'token': self.token,
            'as_user': self.as_user,
        }
        post_msg_data['text'] = msg.get('text', '')
        post_msg_data['attachments'] = msg.get('attachments', [])
        post_msg_response = safe_requests.post(
            response_url, json=post_msg_data)
        return post_msg_response

    def _post_to_channel(self, channel: str, msg: dict):
        msg['attachments'] = json.dumps(msg.get('attachments', []))
        post_msg_data = {
            'token': self.token,
            'channel': channel,
            'as_user': self.as_user,
            'text': '',
            'attachments': []
        }
        post_msg_data.update(msg)
        post_msg_response = safe_requests.post(CHAT_POST_URL, post_msg_data)
        return post_msg_response

    def _post_ephemeral_message(self, request_data, msg: dict):
        msg['attachments'] = json.dumps(msg.get('attachments', []))
        post_msg_data = {
            'token': self.token,
            'user': request_data.user_id,
            'channel': request_data.channel_id,
            'as_user': self.as_user,
            'text': '',
            'attachments': []
        }
        post_msg_data.update(msg)
        post_msg_response = safe_requests.post(
            CHAT_POST_EPHEMERAL_URL, post_msg_data) 
        return post_msg_response

    def _build_broadcast_attach(self, text: str) -> dict:
        attach = {
            "pretext": text,
            "fallback": text,
        }
        return attach

    def _build_feedback_attach(self) -> dict:
        attach = {
            "text": " ",
            "callback_id": "BF",
            "mrkdwn_in": ['pretext', 'text'],
            "footer": (
                "Was this message helpful to you?  Use the buttons below "
                "to let us know!"
            ),
            "actions": [
                {
                    "name": "feedback-positive",
                    "text": ":+1:",
                    "type": "button",
                    "value": "positive"
                },
                {
                    "name": "feedback-negative",
                    "text": ":-1:",
                    "type": "button",
                    "value": "negative"
                }
            ]
        }
        return attach

    def build_img_attach(self, msg, platform_user: PlatformUser) -> dict:
        attachments = []
        for file_data in msg['files']:
            image, extension = self.get_image(file_data)
            key = aws.upload_temp_image(image, extension)
            img_url = aws.generate_presigned_url(key, aws.S3Folders.TEMP)
            attachments.append(
                {
                    'text': '',
                    'image_url': img_url
                }
            )
        msg = {
            'username': platform_user.username,
            'icon_url': platform_user.profile_image,
            'ts': msg.get('ts'),
            'attachments': attachments
        }
        return msg

    def add_forward_footer(self, msg, user_data):
        footer_attach = {
            'text': '',
            'footer': f"sent by {user_data['user_name']} from Teampay",
            'footer_icon': f"{user_data['user_icon_url']}"
        }
        if msg['attachments']:
            msg['attachments'].append(footer_attach)
        else:
            msg['attachments'] = [footer_attach]
        return msg

    def _refresh_access_token(self):
        megatron_user = MegatronUser.objects.first()
        response = safe_requests.post(
            megatron_user.command_url,
            json={
                'command': 'refresh_workspace',
                'megatron_verification_token': megatron_user.verification_token
            }
        )
        response_data = response.json()
        if response_data['ok']:
            data = response_data['data']
            workspace = CustomerWorkspace.objects.get(
                connection_token=self.token
            )
            workspace.name = data['name']
            workspace.domain = data['domain']
            workspace.connection_token = data['connection_token']
            workspace.save()
