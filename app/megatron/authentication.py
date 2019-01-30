from rest_framework import authentication

from django.conf import settings
from django.http import HttpResponse

from megatron.models import Token, MegatronUser


VERIFICATION_TOKEN = settings.MEGATRON_VERIFICATION_TOKEN


def get_organization_token(organization) -> str:
    megatron_user = MegatronUser.objects.get(
        organization_name__iexact=organization.slackteam_set.first().name
    )
    token = Token.objects.get(user=megatron_user).key
    return token


def validate_slack_token(func):
    def wrapper(request):
        data = request.POST
        verification_token = data['token']
        if verification_token == VERIFICATION_TOKEN:
            return func(request)
        else:
            return HttpResponse("Incorrect validation token.", status=401)
    return wrapper


class MegatronTokenAuthentication(authentication.TokenAuthentication):
    keyword = "MegatronToken"

    def get_model(self):
        return Token
