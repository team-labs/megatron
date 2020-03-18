import re
import logging

from django.contrib.auth.models import User

from megatron.models import MegatronChannel
from typing import Optional

LOGGER = logging.getLogger(__name__)


def remove_sensitive_data(msg: dict):
    text = msg.get("text", None)
    try:
        assert isinstance(text, str)
        match = re.search(r"(\d{4}[-\s]?){4}", text)
        if match:
            cleaned_num = re.sub(r"\d", "*", match.group(0))
            cleaned_text = cleaned_num
            msg["text"] = (
                f"{text[:match.start()]}" f"{cleaned_text}" f"{text[match.end()+1:]}"
            )
    except AssertionError:
        LOGGER.warning(
            "Received non-string value for message text during sanitization.",
            extra={"text_value": text},
        )
        msg["text"] = "**** Unexpected ****"

    attachments = msg.get("attachments", [])
    if attachments:
        fields = [a.get("fields", []) for a in attachments]
        flat_fields = [item for sublist in fields for item in sublist]
        for field in flat_fields:
            if field.get("title") == "Card Number":
                field["value"] = "**** **** **** ****"
            elif field.get("title") == "CVV":
                field["value"] = "***"

    return msg


def get_customer_for_megatron_channel(megatron_channel_id: str) -> Optional[dict]:
    try:
        channel = MegatronChannel.objects.get(platform_channel_id=megatron_channel_id)
        return {
            "platform_user_id": channel.platform_user_id,
            "platform_team_id": channel.workspace.platform_id,
        }
    except MegatronChannel.DoesNotExist:
        return None
