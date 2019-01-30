import megatron.commands.command_actions as actions
from megatron.commands import parsing


class Command:
    def __init__(self, text, description, parse, action):
        self.text = text
        self.description = description
        self.action = action
        self.parse = parse

    @staticmethod
    def get_command(command_str):
        return COMMAND_MAPPING.get(command_str)

    def __str__(self):
        return f"Command: {self.text}"


forward_message = Command(
    text='forward',
    description='forward message',
    parse=parsing.get_targeted_user_id,
    action=actions.forward_message)
open_channel = Command(
    text='open',
    description="Who are you trying to connect with?",
    parse=parsing.require_targeted_user_id,
    action=actions.open_channel)
close_channel = Command(
    text='close',
    description="Who's channel are you trying to close?",
    parse=parsing.get_targeted_user_id,
    action=actions.close_channel)
pause_channel = Command(
    text='pause',
    description="Who's bot are you trying to pause?",
    parse=parsing.get_targeted_user_id,
    action=actions.pause_channel)
unpause_channel = Command(
    text='unpause',
    description="Who's bot are you trying to unpause?",
    parse=parsing.get_targeted_user_id,
    action=actions.unpause_channel)
clear_context = Command(
    text='clear-context',
    description="Who's context are you trying to clear?",
    parse=parsing.get_targeted_user_id,
    action=actions.clear_context)
do = Command(
    text='do',
    description="",
    parse=parsing.passthrough,
    action=actions.do
)


COMMAND_MAPPING = {
    'forward': forward_message,
    'open': open_channel,
    'close': close_channel,
    'pause': pause_channel,
    'unpause': unpause_channel,
    'clear-context': clear_context,
    'do': do
}
