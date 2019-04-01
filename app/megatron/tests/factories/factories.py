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
