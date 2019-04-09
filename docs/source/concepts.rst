==================
Concepts and Objects
==================

Diagram of Megatron Processing
------------------------------
.. image:: megatron_flow.png

Description
----------
At its most simple, an API request arrives from a ``Platform`` at an ``Interpreter`` and is converted into an internal
``Command``. The ``Command`` is processed by Megatron and then returned via an outgoing ``Connection`` to the same, or
a different ``platform``.

Concept Definitions
---------------------
* Platform
	A messaging app. A ``platform`` will include corresponding ``Interpreter`` and ``Connection`` APIs.

	In our case, this is just Slack at the moment.

* Interpreter
	The "incoming" API for a platform. Receives messages from the ``Platform`` and passes them on to the
	core Megatron app.

	The ``Interpreter`` sets up any custom URLs a platform may need. As an example, the Slack ``Interpreter``
	provides the URL you set up for slash commands for your Megatron Slack app.

* Command
	A request made to Megatron once it has been converted by an ``Interpreter``. A command is ``Platform``-agnostic.
	Often, but not always, the end result of a ``Command`` is to make a request via a ``Connection``

	This is the core logical unit that Megatron uses internally.

* Connection
	The outgoing API to a ``Platform``. Controls messages sent to the platform and changes them into an actionable shape.
	The core interface is called a ``BotConnection``.
