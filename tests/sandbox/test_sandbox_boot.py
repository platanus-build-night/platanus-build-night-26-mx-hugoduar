import pytest
import docker
from noctua.sandbox.manager import Sandbox


@pytest.fixture
def sandbox():
    s = Sandbox()
    yield s
    s.teardown()


def test_boot_and_teardown(sandbox):
    run = sandbox.boot(image="python:3.12-slim", repo_url=None)
    assert run.container_id
    assert run.state == "ready"
    sandbox.teardown()
    client = docker.from_env()
    with pytest.raises(docker.errors.NotFound):
        client.containers.get(run.container_id)
