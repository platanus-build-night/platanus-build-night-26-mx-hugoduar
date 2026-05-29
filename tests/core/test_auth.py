import pytest
from django.test import RequestFactory
from django.conf import settings
from noctua.core.auth import BearerAuth


def test_bearer_accepts_correct_token(settings):
    settings.NOCTUA_API_TOKEN = "good-token"
    auth = BearerAuth()
    req = RequestFactory().get("/api/queue", HTTP_AUTHORIZATION="Bearer good-token")
    assert auth.authenticate(req, "good-token") == "good-token"


def test_bearer_rejects_wrong_token(settings):
    settings.NOCTUA_API_TOKEN = "good-token"
    auth = BearerAuth()
    req = RequestFactory().get("/api/queue", HTTP_AUTHORIZATION="Bearer wrong-token")
    assert auth.authenticate(req, "wrong-token") is None
