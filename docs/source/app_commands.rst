==================
App Commands
==================
Megatron will occasionally send commands to your app. Your app will need to take action and send an
http response when it receives one of these commands.

The url for a megatron command is configured on ``MegatronUser.command_url``.

The command payload is an http request with a JSON body. The payload
looks like this::

	{
		'command': 'command-name',
		'user_id': 'U12345',
		'megatron_verification_token': 'sometoken'
	}

The possible commands are:

**pause**
	**Expected action**: Mark the `user_id` user as paused/unpaused.

	**Expected response**: 200

**clear-context**
	**Expected action**: Clear any relevant context from the included `user_id`.

	**Expected response**: 200

**search_user**
	**Expected action**: Return a list of platform users based on a
	fuzzy match of the included username.

	**Expected response**: 200 with JSON body::

		{
			"users": [
				{
					"username": {username},
					"platform_user_id": {platform_user_id},
					"platform_team_id": {platform_team_id}
			]
		}


**refresh_workspace**
	**Expected action**: Respond with updated platform credentials.

	**Expected response**: 200 with JSON body::

		{
			"ok": True,
			"data": {
				"name": {platform team name},
				"domain" {platform domain name},
				"connection_token": {platform connection token}
			}
		}

