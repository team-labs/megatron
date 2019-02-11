==================
Megatron Commands
==================
Megatron will occasionally send commands to your app at
/slack_command. Your app will need to take action and send an
http response when it receives one of these commands.

The command payload is an http request with a JSON body. The payload
looks like this::

	{
		'command': 'command-name',
		'user_id': 'U12345',
		'megatron_verification_token': 'sometoken'
	}

The possible commands are:

pause
	**Expected action**: Mark the `user_id` user as paused. Prevent the
	bot from responding to them.

	**Expected response**: 200

unpause
	**Expected action**: Mark the `user_id` user as unpaused. All the
	bot to respond to them.

	**Expected response**: 200

suggest users
	**Expected action**: Return a list of platform users based on a
	fuzzy match of the included username.

	**Expected response**: 200 with JSON body
