from click.testing import CliRunner
from noctua.cli import cli


def test_cli_run_posts_mission(mocker):
    fake_response = mocker.Mock(status_code=201, json=lambda: {"id": 7, "state": "queued"})
    fake_post = mocker.patch("httpx.post", return_value=fake_response)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "--repo", "https://github.com/x/y",
        "--issue", "https://github.com/x/y/issues/1",
        "--goal", "Add /healthz",
    ], env={"NOCTUA_API_URL": "http://localhost:8000", "NOCTUA_API_TOKEN": "t"})
    assert result.exit_code == 0
    assert "mission 7 queued" in result.output.lower()
    fake_post.assert_called_once()
