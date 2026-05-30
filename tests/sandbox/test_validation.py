import pytest
from noctua.sandbox.manager import _validate_repo_url


def test_accepts_valid_github_url():
    _validate_repo_url("https://github.com/owner/repo")
    _validate_repo_url("https://github.com/owner/repo.git")
    _validate_repo_url("https://github.com/owner-1/repo_2")


@pytest.mark.parametrize("bad", [
    "https://github.com/owner/repo; rm -rf /",
    "--upload-pack=evil",
    "http://github.com/owner/repo",  # http not allowed
    "https://example.com/owner/repo",
    "https://github.com/owner",  # no repo segment
    "$(rm -rf /)",
    "https://github.com/o/r && curl evil",
])
def test_rejects_bad_inputs(bad):
    with pytest.raises(ValueError):
        _validate_repo_url(bad)
