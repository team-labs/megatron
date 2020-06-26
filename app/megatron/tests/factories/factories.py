import factory

from megatron import models


class CustomerWorkspaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.CustomerWorkspace

    name = "Fake Workspace"
    platform_type = models.PlatformType.Slack.value
    platform_id = "12345"
    connection_token = "some_connection_token_233"
    domain = "fake_space"


class MegatronUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.MegatronUser

    organization_name = "Decepticons Fake Org"
    verification_token = "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    command_url = "http://no.co"


class MegatronIntegrationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.MegatronIntegration

    megatron_user = factory.SubFactory(MegatronUserFactory)
    platform_type = 1
    platform_id = "T123456"
    connection_token = "xxxxxxxxxxxxxxx"


class MegatronChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.MegatronChannel

    megatron_user = factory.SubFactory(MegatronUserFactory)
    megatron_integration = factory.SubFactory(MegatronIntegrationFactory)
    workspace = factory.SubFactory(CustomerWorkspaceFactory)
    name = "Fake Channel"
    platform_channel_id = "C123456"
    platform_user_id = "U123456"
    is_paused = False
    is_archived = False

    # overwrite `last_message_sent` auto_add_now
    @classmethod
    def _create(cls, target_class, *args, **kwargs):
        last_message_sent = kwargs.pop("last_message_sent", None)
        obj = super(MegatronChannelFactory, cls)._create(target_class, *args, **kwargs)
        if last_message_sent is not None:
            obj.last_message_sent = last_message_sent
            obj.save()
        return obj
