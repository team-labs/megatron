import binascii
import uuid
import os
import enum

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, User, Group

DEFAULT_GROUP_NAME = "admins"


class PlatformType(enum.Enum):
    Slack = 1


class MegatronUser(AbstractBaseUser):
    access_level = (("admin", "Administrator"),)
    organization_name = models.CharField(max_length=255)
    verification_token = models.CharField(max_length=255)
    command_url = models.CharField(max_length=255, null=True, blank=True)

    USERNAME_FIELD = "organization_name"
    REQUIRED_FIELDS = ["organization_name", "access_level"]

    def save(self, *args, **kwargs):
        self.verification_token = str(uuid.uuid4()).replace("-", "")[:24]
        super().save(*args, **kwargs)
        Token.objects.get_or_create(user=self)

    def get_full_name(self):
        return self.organization_name

    def get_short_name(self):
        return self.organization_name


class MegatronIntegration(models.Model):
    megatron_user = models.ForeignKey(MegatronUser, on_delete=models.CASCADE)
    platform_type = models.IntegerField(
        choices=((str(t.value), t.name.title()) for t in PlatformType)
    )  # type: ignore
    platform_id = models.CharField(max_length=255)
    connection_token = models.CharField(max_length=255)

    class Meta:
        unique_together = ("platform_type", "platform_id")


class CustomerWorkspace(models.Model):
    name = models.CharField(max_length=127)
    platform_type = models.IntegerField(
        choices=((str(t.value), t.name.title()) for t in PlatformType)
    )  # type: ignore
    platform_id = models.CharField(max_length=255)
    connection_token = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    class Meta:
        unique_together = ("platform_type", "platform_id")


class MegatronChannel(models.Model):
    megatron_user = models.ForeignKey(MegatronUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    megatron_integration = models.ForeignKey(
        MegatronIntegration, null=True, on_delete=models.CASCADE
    )
    workspace = models.ForeignKey(
        CustomerWorkspace, null=True, on_delete=models.CASCADE
    )
    # This is the commands megatron channel (e.g. zz-Preston)
    platform_channel_id = models.CharField(max_length=63)
    last_message_sent = models.DateTimeField(auto_now_add=True)
    # This is the customer's platform id
    platform_user_id = models.CharField(max_length=127)
    is_paused = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            ("workspace", "platform_channel_id"),
            ("workspace", "platform_user_id"),
        )


class MegatronMessage(models.Model):
    integration_msg_id = models.CharField(max_length=255, blank=True, null=True)
    customer_msg_id = models.CharField(max_length=255, blank=True, null=True)
    megatron_channel = models.ForeignKey(MegatronChannel, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            ("integration_msg_id", "megatron_channel"),
            ("customer_msg_id", "megatron_channel"),
        )


class Token(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(MegatronUser, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super().save(*args, **kwargs)

    def generate_key(self):
        return binascii.hexlify(os.urandom(20)).decode()


class PlatformUser(models.Model):
    platform_id = models.CharField(db_index=True, max_length=10)
    workspace = models.ForeignKey(CustomerWorkspace, on_delete=models.CASCADE)

    # TODO: Better to keep in sync with slack or to refresh live?
    profile_image = models.CharField(max_length=250, default="")
    username = models.CharField(max_length=250, default="")
    display_name = models.CharField(max_length=250, blank=True, null=True)
    real_name = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        unique_together = ("platform_id", "workspace")

    def __str__(self):
        return self.username

    def get_display_name(self):
        if self.display_name:
            return self.display_name
        elif self.real_name:
            return self.real_name
        return self.username
