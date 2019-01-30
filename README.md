Megatron
========

Megatron is a tool that lets you take direct control of your customer-facing
chatbot.

Take a look at Megatron in action:

	gif

Features
--------

Megatron's features are easiest to understand in action. Check out some 
of the lovingly crafted gifs above!
- Send completely custom messages through your bot to users
- Send and receive images and pdfs with users through your bot
- Pause and unpause the bot for specific users
- Force 

Installation
------------

Megatron is a fully featured Django app and generally follows the microservice
pattern. Getting up and running in a production environment is highly dependent
on your existing architecture.

That being said, thanks to Docker, getting running with megatron locally
is essentially a one-step process. Try this: 
1. Clone repo and enter repo
	```
	git clone https://github.com/team-labs/megatron
	cd megatron
	```
2. Run Docker compose
	```
	docker-compose up
	```

##### Point your browser at `localhost:8002` to test that Megatron is running.

Contribute
----------

- Issue Tracker: github.com/team-labs/megatron/issues
- Source Code: github.com/team-labs/megatron

Support
-------

If you are having issues, please let us know.
You can reach me directly at preston@teampay.co

License
-------

The project is licensed under the The Mit License.
