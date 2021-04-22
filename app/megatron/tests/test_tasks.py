import pytest
from freezegun import freeze_time

from megatron.scheduled_tasks import archive_channels
from megatron.tests.factories.factories import (
    MegatronChannelFactory,
    MegatronIntegrationFactory,
    CustomerWorkspaceFactory,
)

pytestmark = pytest.mark.django_db


@freeze_time("2020-09-03")
def test_archive_channels():
    """
    Check that the archive task works as expected, archiving the channels without messages for more than 36 hours
    and unpausing them if necessary
    """
    integration = MegatronIntegrationFactory()
    workspace = CustomerWorkspaceFactory()

    # Channel unaffected, archived and not paused
    ch1 = MegatronChannelFactory(
        megatron_integration=integration,
        workspace=workspace,
        platform_channel_id="CH1",
        platform_user_id="U1",
        is_archived=True,
        is_paused=False,
    )
    # Channel unaffected, not archived but last message sent < 36h
    ch2 = MegatronChannelFactory(
        megatron_integration=integration,
        workspace=workspace,
        platform_channel_id="CH2",
        platform_user_id="U2",
        is_archived=False,
        is_paused=True,
        last_message_sent="2020-09-02 12:00:00",
    )
    # Channel affected, not archived and not paused, should be archived
    ch3 = MegatronChannelFactory(
        megatron_integration=integration,
        workspace=workspace,
        platform_channel_id="CH3",
        platform_user_id="U3",
        is_archived=False,
        is_paused=False,
        last_message_sent="2020-08-15 12:00:00",
    )
    # Channel affected, not archived and paused, should be archived and unpaused
    ch4 = MegatronChannelFactory(
        megatron_integration=integration,
        workspace=workspace,
        platform_channel_id="CH4",
        platform_user_id="U4",
        is_archived=False,
        is_paused=True,
        last_message_sent="2020-08-01 12:00:00",
    )

    archive_channels()

    ch1.refresh_from_db()
    assert ch1.is_archived
    assert not ch1.is_paused

    ch2.refresh_from_db()
    assert not ch2.is_archived
    assert ch2.is_paused

    ch3.refresh_from_db()
    assert ch3.is_archived
    assert not ch3.is_paused

    ch4.refresh_from_db()
    assert ch4.is_archived
    assert not ch4.is_paused
