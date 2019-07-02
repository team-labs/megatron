import pytest

from megatron import models, bot_types, services


@pytest.fixture(autouse=True)
def minimal_megatron_setup():
    megatron_user = models.MegatronUser.objects.create(
        organization_name="Frank's Franks", command_url="www.fakecommandurl.com"
    )
    models.MegatronIntegration.objects.create(
        megatron_user=megatron_user,
        platform_type=1,  # Slack
        platform_id="12345",
        connection_token="faketoken",
    )
    models.CustomerWorkspace.objects.create(
        name="Customer of Frank",
        platform_type=1,  # Slack
        platform_id="9876",
        connection_token="alsoafaketoken",
    )


@pytest.fixture(autouse=True)
def no_bot_connections(monkeypatch):
    class FakeConnection:
        def take_action(self, action):
            return {"ok": True}

        def broadcast(self, text, user_id, capture_feedback):
            return {"ok": True}

        def incoming(self, msg):
            return {"ok": True}

        def clear_context(self, user_id):
            return {"ok": True}

        def create_channel(self, channel_name):
            return {"ok": True, "channel": {"id": "FAKEID"}}

        def message(self, response_channel, new_msg):
            return {"ok": True, "message": {"ts": 12333.4444}}

        def respond_to_url(self, response_channel, new_msg):
            return {"ok": True}

        def open_im(self, platform_user_id):
            return {"ok": True, "channel": {"id": "FAKEID"}}

        def im_history(self, channel_id, num_messages):
            return {"ok": True, "messages": []}

        def update_msg(self, message_ts, channel_id, join_message):
            return {"ok": True}

        def dm_user(self, slack_id, msg):
            return {"ok": True, "ts": "1234.5678"}

        def ephemeral_message(self, response_channel, response_user, msg):
            return {"ok": True}

    def fake_get_bot_connection(self, as_user=False):
        return FakeConnection()

    monkeypatch.setattr(
        bot_types.BotType, "get_bot_connection", fake_get_bot_connection
    )
    monkeypatch.setattr(
        bot_types.BotType,
        "get_bot_connection_from_platform_id",
        fake_get_bot_connection,
    )
    monkeypatch.setattr(
        services.IntegrationService, "get_connection", fake_get_bot_connection
    )
    monkeypatch.setattr(
        services.WorkspaceService, "get_connection", fake_get_bot_connection
    )
