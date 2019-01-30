from celery import shared_task

from datetime import timedelta, datetime, timezone

from megatron.models import MegatronChannel, MegatronIntegration, CustomerWorkspace
from megatron.services import IntegrationService, MegatronChannelService, WorkspaceService
from megatron.interpreters.slack import formatting

PAUSE_WARNING_START = timedelta(minutes=3)
PAUSE_WARNING_STOP = PAUSE_WARNING_START + timedelta(minutes=1)
ARCHIVE_TIME = timedelta(hours=36)


@shared_task
def refresh_platform_user_data():
    for workspace in CustomerWorkspace.objects.all():
        WorkspaceService(workspace).refresh_user_data()


@shared_task
def unpause_reminder():
    channels = MegatronChannel.objects.all()
    for channel in channels:
        if not channel.is_paused:
            continue
        workspace_id = channel.workspace.id
        platform_user_id = channel.platform_user_id
        time_since_last_message = (
            datetime.now() - channel.last_message_sent)
        if PAUSE_WARNING_START < time_since_last_message <= PAUSE_WARNING_STOP:
            integration = MegatronIntegration.objects.get(
                megatron_user=channel.megatron_user
            )
            connection = IntegrationService(
                integration).get_connection(as_user=False)
            msg = formatting.get_pause_warning(workspace_id, platform_user_id)
            connection.message(channel.platform_channel_id, msg)


@shared_task
def archive_channels():
    archive_time = datetime.now(timezone.utc) - ARCHIVE_TIME
    channels = MegatronChannel.objects.filter(
        is_archived=False,
        last_message_sent__lte=archive_time
    )
    for channel in channels:
        MegatronChannelService(channel).archive()
