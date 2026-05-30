import pytest
from django.test import Client
from noctua.core.models import Producer

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.NOCTUA_API_TOKEN = "t"
    Producer.objects.create(key="pr", kind="pr", rubric_md="initial", default_budget={})

def auth():
    return {"HTTP_AUTHORIZATION": "Bearer t"}

def test_list_producers():
    c = Client()
    r = c.get("/api/producers", **auth())
    assert r.status_code == 200
    assert any(p["key"] == "pr" for p in r.json())

def test_update_rubric():
    c = Client()
    r = c.put("/api/producers/pr/rubric", data={"rubric_md": "new rubric content"}, content_type="application/json", **auth())
    assert r.status_code == 200
    assert Producer.objects.get(key="pr").rubric_md == "new rubric content"
