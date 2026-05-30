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

@pytest.mark.django_db
def test_producers_toolkits_returns_union_of_required_and_optional(settings):
    settings.NOCTUA_API_TOKEN = "t"
    from noctua.producers import registry as preg

    class A:
        required_toolkits = ["LINKEDIN", "TWITTER"]
        optional_toolkits = []
    class B:
        required_toolkits = ["NOTION"]
        optional_toolkits = ["GMAIL"]

    # Snapshot the cache (which the API's _warm_producer_cache populated with
    # real producers) and replace it with only our fakes, then restore on exit.
    snapshot = dict(preg._cache)
    preg._cache.clear()
    preg._cache["a"] = A()
    preg._cache["b"] = B()
    try:
        c = Client()
        r = c.get("/api/producers/toolkits", **auth())
        assert r.status_code == 200
        # Only toolkits referenced by producers currently in the cache, deduped, sorted.
        assert sorted(r.json()["toolkits"]) == ["GMAIL", "LINKEDIN", "NOTION", "TWITTER"]
    finally:
        preg._cache.clear()
        preg._cache.update(snapshot)
