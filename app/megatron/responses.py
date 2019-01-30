import json

from django.http import HttpResponse


class MegatronResponse(HttpResponse):
    def __init__(self, json_data, status, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = json.dumps(json_data)
        self.status_code = status
        self.content_type = 'application/json'


OK_RESPONSE = MegatronResponse({'ok': True}, 200)
