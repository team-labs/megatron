import requests

from django.conf import settings

from megatron import utils
from megatron.models import MegatronUser
from megatron.errors import MegatronException


def get_targeted_user_id(args: list, command, response_channel):
    if len(args) == 1:
        targeted_user_name = args[0]
        #TODO: Remove megatron user
        command_url = MegatronUser.objects.first().command_url
        response = requests.post(
            command_url, json={
                'megatron_verification_token': settings.MEGATRON_VERIFICATION_TOKEN,
                'command': 'search_user',
                'targeted_user_name': targeted_user_name
            }
        )
        potential_users = response.json()['users']
        if not potential_users:
            raise MegatronException(
                {'text': "I really don't know who that is. Try again?"})
        elif len(potential_users) == 1:
            targeted_user = potential_users[0]
        else:
            response = _disambiguate_response(
                potential_users, command)
            raise MegatronException(response)

    elif len(args) == 0:
        targeted_user = utils.get_customer_for_megatron_channel(
            response_channel)
        if targeted_user is None:
            raise MegatronException(
                {'text': 'Please specify a user for this command.'})

    else:
        raise MegatronException(
            {'text': "Too many arguments to command. Expecting two."})

    return {'targeted_platform_id': targeted_user['platform_user_id']}


def require_targeted_user_id(args: list, command, response_channel):
    try:
        return get_targeted_user_id(args, command, response_channel)
    except KeyError:
        raise MegatronException({'text': "Give me a little help! Who do you want to speak with?"})



def _disambiguate_response(users, command):
    options = []
    for user in users:
        options.append(
            {
                'text': f"{user['username']}",
                'value': f"{user['platform_team_id']}-{user['platform_user_id']}"
            }
        )

    return {
        'response_type': 'ephemeral',
        'attachments': [
            {
                'callback_id': f'{command.text}',
                'text': command.description,
                'actions': [
                    {
                        'name': 'user_select',
                        'text': 'Select a user',
                        'type': 'select',
                        'options': options
                    }
                ]
            }
        ]
    }


def passthrough(args: list, command, response_channel):
    return {'arguments': ' '.join(args)}

