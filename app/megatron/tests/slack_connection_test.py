import pytest
from unittest.mock import MagicMock
from megatron.connections import slack
from megatron.tests.factories import factories


pytestmark = pytest.mark.django_db


def test_get_user_info():
    workspace = factories.CustomerWorkspaceFactory()
    connection = slack.SlackConnection(workspace.connection_token)
    irrelevant_user_id = "U12345"
    connection._refresh_access_token = MagicMock()
    connection._get_user_info(irrelevant_user_id)
    connection._refresh_access_token.assert_called_once()


@pytest.mark.django_db
def test_customer_workspace_refresh(fake_app_response):
    workspace = factories.CustomerWorkspaceFactory()
    connection = slack.SlackConnection(workspace.connection_token)
    irrelevant_user_id = "U12345"
    connection._refresh_access_token(irrelevant_user_id)
    workspace.refresh_from_db()

    assert workspace.name == "BORKBORK"
    assert workspace.domain == "BORKBORKBORK"
    assert workspace.connection_token == "BORK_BORK_BORK_BORK"
