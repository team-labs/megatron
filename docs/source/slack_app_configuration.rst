.. _megatron_slack_configuration:

Slack App Configuration
====================================
To use Megatron on Slack, you'll need to set up and configure a
custom Slack app.

#. Navigate to https://api.slack.com/apps and click "Create New App"
#. Set up app basics

	* Click "Basic Information" on the left side of the screen
	* Save the "Verification Token" you will need it when setting up your environmental variables
	* Enter whatever you'd like under "Display Information"
	* Click "Save Changes"

#. Enable "Interactive Components" so that your app can use buttons and drop-downs

	* Click "Interactive Components" on the left side of the screen
	* Change the switch in the top-right to "On"
	* Under "Request URL" enter ``<your_app>/megatron/slack/interactive-message/``
	* Click "Save Changes"

#. Enable "Slash Commands" so that your app can use...slash commands

	* Click "Slash Commands" on the left side of the screen
	* Click "Create New Command"
	* Provide whatever name and description you want for the command (We like "/megatron"!)
	* Next to "Request URL" enter ``<your_app>/megatron/slack/slash-command/``
	* Click "Save Changes"

#. Add oAuth Scopes

	* Click "OAuth & Permissions"
	* Under "Scopes" add the following:

		* ``channels:history``
		* ``channels:read``
		* ``channels:write``
		* ``chat:write:bot``
		* ``commands``
		* ``users:read``

#. Enable "Event Subscriptions" so that your app is notified of new messages in Megatron channels

	* Click "Event Subscriptions" on the left side of the screen
	* Change the switch in the top-right to "On"
	* Under "Request URL" enter ``<your_app>/megatron/slack/event/``
	* Under "Subscribe to Workspace Events" search for and add ``message.channels``
	* Click "Save Changes"

**You're done!**
