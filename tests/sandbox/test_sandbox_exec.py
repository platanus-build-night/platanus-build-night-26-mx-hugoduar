import pytest
from noctua.sandbox.manager import Sandbox


@pytest.fixture
def sandbox():
    s = Sandbox()
    s.boot("python:3.12-slim", None)
    yield s
    s.teardown()


def test_exec_returns_stdout(sandbox):
    r = sandbox.exec(["python", "-c", "print('hi')"])
    assert r.exit_code == 0
    assert "hi" in r.stdout


def test_write_and_read_file(sandbox):
    sandbox.write_file("/work/x.txt", b"hello")
    assert sandbox.read_file("/work/x.txt") == b"hello"


def test_exec_nonzero(sandbox):
    r = sandbox.exec(["bash", "-lc", "exit 7"])
    assert r.exit_code == 7
