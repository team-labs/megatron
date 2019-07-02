import logging


LOGGER = logging.getLogger(__name__)


def get_organization_token(self):
    try:
        token = self.organization.slack_bot.slack_access_token
    except AttributeError:
        LOGGER.exception(
            "Unable to locate Slack Bot for organization: {}".format(self.organization)
        )
        return
    return token
