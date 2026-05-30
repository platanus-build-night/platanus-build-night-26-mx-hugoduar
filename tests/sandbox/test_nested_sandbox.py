import pytest
from noctua.sandbox.manager import NestedSandbox


@pytest.fixture
def nested():
    s = NestedSandbox()
    s.boot("python:3.12-slim", None)
    yield s
    s.teardown()


def test_nested_has_no_network(nested):
    r = nested.exec(["bash", "-lc", "getent hosts google.com || echo offline"])
    assert "offline" in r.stdout


def test_nested_runs_python(nested):
    r = nested.exec(["python", "-c", "print(2+2)"])
    assert r.exit_code == 0 and "4" in r.stdout
