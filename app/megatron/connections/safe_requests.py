import requests
from logging import getLogger

from megatron.responses import MegatronResponse


LOGGER = getLogger(__name__)


class SafeRequest:
    def __init__(self, response_verification, get_response_data):
        self.response_verification = response_verification
        self.get_response_data = get_response_data

    def safe_requests(self, method, url, *args, **kwargs):
        if not kwargs.get('timeout'):
            timeout = 10
        else:
            timeout = kwargs.get('timeout')
        try:
            response = requests.request(method, url, *args, **kwargs,
                                        timeout=timeout)
        except requests.Timeout:
            LOGGER.exception("Megatron request timed out.")
            return MegatronResponse({'ok': False, 'error': 'Timeout error'}, 500)

        try:
            verified = self.response_verification(response)
            response_data = self.get_response_data(response)
        except:
            LOGGER.exception("Error attempting to verify response from platform.")
            return response

        if not verified:
            LOGGER.exception("Recieved error response from platform.",
                             extra={'response': response_data})

        return response

    def post(self, url, data=None, json=None, **kwargs):
        return self.safe_requests('post', url, data=data, json=json, **kwargs)

    def get(self, url, data=None, json=None, **kwargs):
        return self.safe_requests('get', url, data=data, json=json, **kwargs)