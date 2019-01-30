from django.conf.urls import url
from megatron import api, root
from django.urls import include
from megatron.interpreters.slack import urls as slack_urls


megatron_patterns = [
    url(r'^$', api.test),


    # API - Actions
    url(r'incoming/', api.incoming),
    url(r'outgoing/', api.outgoing),
    url(r'broadcast/', api.broadcast),
    url(r'edit/', api.edit),
    url(r'message/(?P<user_id>[0-9A-Za-z]+)/', api.message),
    url(r'notify-user/', api.notify_user),
    url(r'get-a-human/$', api.get_a_human),

    # API - Maintenance
    url(r'register-workspace/$', api.register_workspace)
]

# TODO: Make dynamic for enabled interpreters
megatron_patterns.extend(slack_urls.URLS)


urlpatterns = [
    url(r'^$', root.root),
    url(r'megatron/', include(megatron_patterns)),
]
