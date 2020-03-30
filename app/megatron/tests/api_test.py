import json
import pytest

from django.test import RequestFactory
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate
from megatron.interpreters.slack import api as slack_api

from megatron import api, models

pytestmark = pytest.mark.django_db
RF = APIRequestFactory()


@pytest.fixture(autouse=True)
def authenticate_request_factory(monkeypatch):
    def authenticate_request(func):
        admin_user = User.objects.create_user("test", "testguy", "pw")
        admin_user.is_staff = True
        admin_user.save()

        def auth(*args, **kwargs):
            request = func(*args, **kwargs)
            force_authenticate(request, admin_user)
            return request

        return auth

    monkeypatch.setattr(
        APIRequestFactory, "post", authenticate_request(APIRequestFactory.post)
    )


class TestBroadcast(object):
    @staticmethod
    @pytest.fixture
    def broadcast_payload():
        payload = {
            "text": json.dumps({"text": "Sample text!"}),
            "broadcasts": [
                {
                    "platform_type": "slack",
                    "org_id": "9876",
                    "user_ids": ["1234", "asdf", "aserf"],
                }
            ],
        }
        return payload

    def test_broadcast_success(self, broadcast_payload):
        request = RF.post(
            "/broadcast/",
            json.dumps(broadcast_payload),
            content_type="application/json",
        )
        response = api.broadcast(request)
        assert response.status_code == 200
        assert json.loads(response.content)["ok"]

    @pytest.mark.parametrize("missing_param", [("broadcasts"), ("text")])
    def test_broadcast_error(self, broadcast_payload, missing_param):
        del broadcast_payload[missing_param]
        request = RF.post(
            "/broadcast/",
            json.dumps(broadcast_payload),
            content_type="application/json",
        )
        response = api.broadcast(request)
        assert response.status_code == 400
        assert missing_param in json.loads(response.content)["error"]


class TestIncomingMessage(object):
    @staticmethod
    @pytest.fixture
    def incoming_payload():
        payload = {
            "team": "9876",
            "message": {"user": "D12355", "text": "I am a message!"},
        }
        return payload

    def test_incoming_message(self, incoming_payload):
        megatron_user = models.MegatronUser.objects.first()
        request = RF.post("/incoming/", incoming_payload, format="json")
        force_authenticate(request, megatron_user)
        response = api.incoming(request)
        assert response.status_code == 200
        assert json.loads(response.content)["ok"]


class TestRegisterOrganization(object):
    @staticmethod
    @pytest.fixture
    def fake_request():
        incoming_payload = {
            "name": "Some Fake Workspace",
            "platform_type": "slack",
            "platform_id": "12345",
            "domain": "fake_domain",
            "connection_token": "BLAHTOKENTOKENTOKEN",
        }
        request = RF.post("/register_organization/", incoming_payload, format="json")
        return request

    def test_register_organization(self, fake_request):
        response = api.register_workspace(fake_request)
        assert response.status_code == 200
        workspace = models.CustomerWorkspace.objects.filter(
            name="Some Fake Workspace"
        ).first()
        assert workspace is not None
        assert workspace.domain == "fake_domain"
