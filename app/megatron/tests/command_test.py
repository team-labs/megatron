import pytest


from megatron.commands import command_actions
from megatron.models import (
    MegatronChannel, MegatronUser, MegatronIntegration, CustomerWorkspace,
    PlatformUser
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_platform_user():
    user = PlatformUser.objects.create(
        platform_id=12345,
        workspace=CustomerWorkspace.objects.first(),
        profile_image='no.co',
        username="fakeuser"
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
        platform_channel_id="zz-fakechannel"
    )
    return channel


@pytest.fixture(autouse=True)
def fake_request_data(fake_channel):
    return {
        'channel_id': fake_channel.platform_channel_id,
        'user_id': fake_channel.platform_user_id,
        'response_url': 'totally.fake.co'
    }


@pytest.fixture
def fake_arguments(fake_platform_user):
    return {'targeted_platform_id': fake_platform_user.platform_id}


class TestOpenChannel(object):
    @staticmethod
    @pytest.fixture(autouse=True)
    def no_delay_update():
        command_actions._update_channel_link.delay = (
            command_actions._update_channel_link)

    def test_open_channel_creates_channel(
            self, fake_request_data, fake_arguments):
        megatron_user = MegatronUser.objects.first()
        response = command_actions.open_channel(
            megatron_user.id, fake_request_data, fake_arguments)
        new_channel = MegatronChannel.objects.first()
        assert response['ok'] is True
        assert new_channel.workspace.name == "Customer of Frank"
        assert new_channel.platform_user_id == "12345"


class TestForwardMessage(object):
    def test_forward_message(self, fake_channel):
        msg = {'text': 'I am a fake message.', 'ts': '1234'}
        response = command_actions.forward_message(
            fake_channel.platform_channel_id, msg, {})
        assert response['ok'] is True


class TestPauseChannel(object):
    @staticmethod
    @pytest.fixture(autouse=True)
    def no_post(monkeypatch):
        def fake_post(*args, **kwargs):
            class Response:
                status_code = 200
            return Response()

        monkeypatch.setattr(command_actions.requests, 'post', fake_post)

    @pytest.mark.parametrize(
        "pause_func, paused", [
            (command_actions.pause_channel, True),
            (command_actions.unpause_channel, False)
        ]
    )
    def test_pause_channel(self, pause_func, paused, fake_arguments,
                           fake_request_data):
        megatron_user = MegatronUser.objects.get(
            organization_name="Frank's Franks")
        response = pause_func(megatron_user.id, fake_request_data, fake_arguments)
        megatron_channel = MegatronChannel.objects.get(
            platform_channel_id=fake_request_data['channel_id'])
        assert response['ok'] is True
        assert megatron_channel.is_paused is paused
