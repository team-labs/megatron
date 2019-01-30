from django.conf.urls import url
from megatron.interpreters.slack import api


URLS = [
    url(r'slack/slash-command/', api.slash_command),
    url(r'slack/interactive-message/', api.interactive_message),
    url(r'slack/event/', api.event),
]


