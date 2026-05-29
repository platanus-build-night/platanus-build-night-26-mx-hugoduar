import pytest
from django.test import Client
from django.conf import settings

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def token(settings):
    settings.NOCTUA_API_TOKEN = "test-token"

def auth():
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}

def test_create_mission():
    c = Client()
    r = c.post(
        "/api/missions",
        data={"goal": "Add /healthz", "producer_key": "pr", "repo_url": "https://github.com/x/y"},
        content_type="application/json",
        **auth(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "queued"
    assert body["id"]

def test_get_mission():
    c = Client()
    create = c.post("/api/missions", data={"goal": "g", "producer_key": "pr", "repo_url": "r"}, content_type="application/json", **auth()).json()
    r = c.get(f"/api/missions/{create['id']}", **auth())
    assert r.status_code == 200
    assert r.json()["goal"] == "g"

def test_unauthenticated_rejected():
    c = Client()
    r = c.get("/api/missions/1")
    assert r.status_code == 401
