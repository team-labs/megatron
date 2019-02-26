import hmac
import hashlib

from django.conf import settings
from django.http import HttpResponse
from rest_framework import authentication

from megatron.responses import NOT_AUTHORIZED_RESPONSE
from megatron.models import Token, MegatronUser


VERIFICATION_TOKEN = settings.MEGATRON_VERIFICATION_TOKEN


def get_organization_token(organization) -> str:
    megatron_user = MegatronUser.objects.get(
        organization_name__iexact=organization.slackteam_set.first().name
    )
    token = Token.objects.get(user=megatron_user).key
    return token


def verify_slack_response(request: HttpResponse) -> bool:
    signing_key = settings.SLACK_SIGNING_KEY.encode('utf-8')
    slack_timestamp = request.META['HTTP_X_SLACK_REQUEST_TIMESTAMP']
    body = request.body.decode('utf-8')
    basestring = f"v0:{slack_timestamp}:{body}".encode('utf-8')
    digest = "v0=" + hmac.new(signing_key, msg=basestring, digestmod=hashlib.sha256).hexdigest()
    if hmac.compare_digest(request.META['HTTP_X_SLACK_SIGNATURE'], digest):
        return True
    return False


def validate_slack_signed_secret(func):
    def wrapper(request):
        if verify_slack_response(request):
            return func(request)
        else:
            return NOT_AUTHORIZED_RESPONSE
    return wrapper


class MegatronTokenAuthentication(authentication.TokenAuthentication):
    keyword = "MegatronToken"

    def get_model(self):
        return Token
