.. _environment_setup:

Environment Setup
====================================

PYTHONUNBUFFERED
	Always "1". Sends logs and print statements directly to the console.


DJANGO_PORT
	Port that Django will use to listen for incoming requests. Should generally
	not be changed from 8002.

HOSTNAME
	The root url that this instance of Django will run at. Using `ngrok <https://ngrok.com/>`_
	is suggested.

DATABASE_URL
	URL of the database on which to store Megatron data. Don't use the same database
	as another Django app.

REDIS_URL
	Megatron uses celery to queue tasks through redis.

CHANNEL_PREFIX
	The prefix for channels that Megatron creates to talk to users.

MEGATRON_VERIFICATION_TOKEN
	Verification token sent with Slack requests. Get from your Megatron Slack app if
	needed.

MEGATRON_APP_MODE
	``megatron-dev`` for development environments. ``megatron-production`` for production.


We're using S3 as a stopover here but this can be done through Slack as well. Great
spot for a PR.

S3_AWS_ACCESS_KEY_ID
	Access key for your AWS instance. Megatron uses AWS S3 to store images it
	passes from one messaging workspace to another.

S3_AWS_SECRET_ACCESS_KEY
	Ditto but this one's secret.

AWS_S3_BUCKET
	Name of the bucket to store images that Megatron processes