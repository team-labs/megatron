.. Megatron documentation master file, created by
   sphinx-quickstart on Tue Jan 29 17:56:31 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Megatron
====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   megatron_commands
   slack_app_configuration
   environment_setup

Requirements
===================================
Before you setup Megatron you should make sure you have:

1. A database instance running on your local machine
2. | A redis instance running on your local machine
   | (Any cache should work here but only redis is tested)

Quickstart
====================================
The objective of this document is to get Megatron up and running in your
local environment as fast as possible. To start:

#. Clone and enter repo::

	git clone https://github.com/team-labs/megatron
	cd megatron

#. Set up an app for Megatron

	This step depends on the app or apps you want to use with
	Megatron:

	* Slack: :ref:`megatron_slack_configuration`

#. Setup your environment

	* In your project, make a copy of ``django-variables.env.default`` in the ``app`` directory.
	* Rename the copy ``django-variables.env``.
	* Edit the values in ``django-variables.env`` to match your configuration.
	See here for help with environmental variables: :ref:`environment_setup`

#. Run Docker compose::

**Finally, point your browser at "localhost:8002" to test that Megatron is running.**
