Quickstart
====================================
The objective of this document is to get Megatron up and running in your
local environment as fast as possible. To start:

#. Clone and enter repo::

	git clone https://github.com/team-labs/megatron
	cd megatron

#. Set up an app for Megatron

	This step depends on the app or apps you want to use with
	Megatron

	* Slack: :ref:`megatron_slack_configuration`

#. Setup your environment

	* In your project, make a copy of ``django-variables.env.default`` in the ``app`` directory.
	* Rename the copy ``django-variables.env``.
	* Edit the values in ``django-variables.env`` to match your configuration.
	See here for help with environmental variables: :ref:`environment_setup`

#. Run Docker compose::

	docker-compose up

**Finally, point your browser at "localhost:8002" to test that Megatron is running.**

