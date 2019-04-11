# TODO: Create a formatting directory and name this Slack as its
# all Slack specific formatting.

from megatron.models import MegatronChannel, PlatformUser

class Colors:
    gold = "ff9e16"
    orange = "e15829"
    navy = "1f355e"
    grey = "cac8c8"
    green = "006F14"
    red = "E13704"


def user_titled(platform_user_id: str, text: str) -> dict:
    platform_user = PlatformUser.objects.get(platform_id=platform_user_id)
    username = platform_user.username + "@" + platform_user.workspace.domain
    msg = {
        "attachments": [
            {
                "text": text,
                "title": username
            }
        ]
    }
    return msg


def get_pause_warning(workspace_id: str, platform_user_id: str):
    msg = {
        "text": "",
        "attachments": [
            {
                "title": "Paused",
                "text": (
                    "The bot for this user is paused. It will not "
                    "respond to any messages sent to it."
                ),
                "color": Colors.gold,
                "actions": [
                    {
                        "name": "unpause",
                        "type": "button",
                        "text": "Unpause Bot",
                        "value": f'{workspace_id}-{platform_user_id}'
                    }
                ],
                "callback_id": "unpause",
                "fallback": " "
            }
        ]
    }
    return msg


def get_unpaused_warning(workspace_id: str, platform_user_id: str):
    msg = {
        "text": "",
        "attachments": [
            {
                "title": "Bot is not paused.",
                "text": (
                    "The bot for this user is not paused. It will continue "
                    "to respond to their messages."
                ),
                "color": Colors.orange,
                "actions": [
                    {
                        "name": "pause",
                        "type": "button",
                        "text": "Pause Bot",
                        "value": f'{workspace_id}-{platform_user_id}'
                    }
                ],
                "callback_id": "pause",
                "fallback": " "
            }
        ]
    }
    return msg
