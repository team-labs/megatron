import json
import pytest

from django.test import RequestFactory
from rest_framework.test import force_authenticate

from megatron.commands import command_actions
from megatron.interpreters.slack import api as slack_api
from megatron.models import (
    CustomerWorkspace,
    PlatformUser,
    MegatronChannel,
    MegatronUser,
    MegatronIntegration,
    PlatformAgent,
)

pytestmark = pytest.mark.django_db
factory = RequestFactory()


@pytest.fixture(autouse=True)
def fake_platform_user():
    user = PlatformUser.objects.create(
        platform_id=12345,
        workspace=CustomerWorkspace.objects.first(),
        profile_image="no.co",
        username="fakeuser",
    )
    return user


@pytest.fixture(autouse=True)
def fake_platform_agent():
    user = PlatformAgent.objects.create(
        platform_id=54321,
        integration=MegatronIntegration.objects.first(),
        profile_image="no.co",
        username="fakeagent",
    )
    return user


@pytest.fixture(autouse=True)
def fake_channel(fake_platform_user):
    channel = MegatronChannel.objects.create(
        megatron_user=MegatronUser.objects.first(),
        workspace=fake_platform_user.workspace,
        name="fakechannel",
        platform_user_id=fake_platform_user.platform_id,
        megatron_integration=MegatronIntegration.objects.first(),
        platform_channel_id="zz-fakechannel",
    )
    return channel


class TestInteractiveMessage(object):
    @staticmethod
    @pytest.fixture
    def no_delay_actions():
        def no_forward_message(channel, msg, from_user=None):
            return {"ok": True}

        command_actions.open_channel.delay = command_actions.open_channel
        command_actions.close_channel.delay = command_actions.close_channel
        command_actions.pause_channel.delay = command_actions.pause_channel
        command_actions.unpause_channel.delay = command_actions.unpause_channel
        command_actions.clear_context.delay = command_actions.clear_context
        command_actions.forward_message = no_forward_message

    @staticmethod
    @pytest.fixture
    def interactive_payload_button():
        payload = {
            "actions": [{"type": "button", "value": "9876-12345"}],
            "callback_id": "",
            "team": {"id": "12345"},
            "channel": {"id": "xxxxx"},
            "user": {"id": "54321"},
            "response_url": "xxxxx",
        }
        return payload

    @staticmethod
    @pytest.fixture
    def interactive_payload_select():
        payload = {
            "type": "interactive_message",
            "actions": [
                {"type": "select", "selected_options": [{"value": "9876-12345"}],}
            ],
            "callback_id": "",
            "team": {"id": "12345"},
            "channel": {"id": "xxxxx"},
            "user": {"id": "54321"},
            "response_url": "xxxxx",
        }
        return payload

    def test_interactive_message(
        self,
        interactive_payload_button,
        interactive_payload_select,
        no_delay_actions,
        fake_app_response,
    ):
        commands = ["open", "close", "pause", "unpause", "clear-context"]
        megatron_user = MegatronUser.objects.first()

        for command in commands:
            interactive_payload_button["callback_id"] = command
            interactive_payload_select["callback_id"] = command

            request_button = factory.post(
                "/slack/interactive-message/",
                {"payload": json.dumps(interactive_payload_button)},
            )
            request_select = factory.post(
                "/slack/interactive-message/",
                {"payload": json.dumps(interactive_payload_select)},
            )

            force_authenticate(request_button, megatron_user)
            force_authenticate(request_button, megatron_user)

            response_button = slack_api.interactive_message(request_select)
            response_select = slack_api.interactive_message(request_select)

            assert response_button.status_code == 200
            assert response_select.status_code == 200


class TestEventIgnoredBotMessage:
    @staticmethod
    @pytest.fixture
    def fake_data():
        return {
            "api_app_id": "AABCN8V7W",
            "authed_users": [["UBDS231"]],
            "type": "event_callback",
            "event": {
                "channel": "CB2JNGD5Y",
                "channel_type": "channel",
                "event_ts": "1548042126.003600",
                "hidden": True,
                "type": "message",
                "message": {
                    "attachments": [],
                    "bot_id": "BAE156LLF",
                    "subtype": "bot_message",
                    "text": "",
                    "ts": "1548041701.003100",
                    "type": "message",
                    "username": "Megatron",
                },
            },
        }

    def test(self, fake_data):
        MegatronChannel.objects.create(
            megatron_user=MegatronUser.objects.create(),
            platform_channel_id=fake_data["event"]["channel"],
            megatron_integration=MegatronIntegration.objects.first(),
            workspace=CustomerWorkspace.objects.first(),
        )

        request = RequestFactory().post(
            "/slack/event/", content_type="application/json", data=fake_data
        )
        response = slack_api.event(request)
        assert response.status_code == 200
