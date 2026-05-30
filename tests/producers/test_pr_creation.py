"""Tests for the create_pr_for_artifact Celery task and its API endpoint."""
import pytest
from unittest.mock import patch, MagicMock, call as mock_call
from django.test import Client
from noctua.core.models import Mission, Artifact

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def token(settings):
    settings.NOCTUA_API_TOKEN = "tt"


def auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}


@pytest.fixture
def mission():
    return Mission.objects.create(
        goal="Fix login bug",
        producer_key="pr",
        repo_url="https://github.com/hugoduar/noctua-demo-app",
        budget={"max_wall_seconds": 1800},
    )


@pytest.fixture
def pr_artifact(mission):
    return Artifact.objects.create(
        mission=mission,
        producer_key="pr",
        kind="pr",
        uri="",
        preview={"title": "Fix login crash"},
        provenance={},
        validation={"tests": "passed"},
        queue_state="pending",
    )


@pytest.fixture
def mock_sandbox():
    """Return a patched Sandbox class whose instances have pre-configured exec results."""
    ok_result = MagicMock(exit_code=0, stdout="", stderr="")
    pr_result = MagicMock(exit_code=0, stdout="https://github.com/hugoduar/noctua-demo-app/pull/42\n", stderr="")

    with patch("noctua.runner.tasks.Sandbox") as SandboxCls:
        instance = MagicMock()
        # exec returns ok for everything except gh pr create
        instance.exec.return_value = ok_result
        # make gh pr create return the PR URL (last exec call in happy path)
        instance.exec.side_effect = None
        instance.exec.return_value = ok_result

        def smart_exec(cmd, **kwargs):
            joined = " ".join(str(c) for c in cmd)
            if "gh pr create" in joined:
                return pr_result
            return ok_result

        instance.exec.side_effect = smart_exec
        SandboxCls.return_value = instance
        yield SandboxCls, instance


# ---------------------------------------------------------------------------
# Task: happy path
# ---------------------------------------------------------------------------

class TestCreatePrForArtifactTask:
    def test_boots_sandbox_with_correct_repo_url(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        SandboxCls, instance = mock_sandbox

        create_pr_for_artifact(pr_artifact.id)

        # Sandbox was constructed with mission_id
        SandboxCls.assert_called_once()
        kwargs = SandboxCls.call_args.kwargs
        assert kwargs["mission_id"] == pr_artifact.mission_id

        # boot was called with the mission's repo_url
        instance.boot.assert_called_once_with(
            image="python:3.12-slim",
            repo_url="https://github.com/hugoduar/noctua-demo-app",
        )

    def test_runs_branch_commit_push_pr_in_order(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        create_pr_for_artifact(pr_artifact.id)

        exec_calls = instance.exec.call_args_list
        # Each call is exec([cmd, ...]) — flatten to joined strings for easy assertions
        joined = [" ".join(str(c) for c in ca.args[0]) for ca in exec_calls]

        branch_idx = next(i for i, s in enumerate(joined) if "checkout -b" in s)
        commit_idx = next(i for i, s in enumerate(joined) if "git" in s and "commit" in s)
        push_idx = next(i for i, s in enumerate(joined) if "git push" in s)
        pr_idx = next(i for i, s in enumerate(joined) if "gh pr create" in s)

        assert branch_idx < commit_idx < push_idx < pr_idx, (
            f"expected branch({branch_idx}) < commit({commit_idx}) < push({push_idx}) < pr({pr_idx})"
        )

    def test_updates_artifact_uri_on_success(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact

        create_pr_for_artifact(pr_artifact.id)

        pr_artifact.refresh_from_db()
        assert pr_artifact.uri == "https://github.com/hugoduar/noctua-demo-app/pull/42"

    def test_writes_noctua_md_with_mission_content(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        create_pr_for_artifact(pr_artifact.id)

        instance.write_file.assert_called_once()
        path, content = instance.write_file.call_args.args
        assert path == "/work/NOCTUA.md"
        decoded = content.decode()
        assert f"artifact #{pr_artifact.id}" in decoded
        assert f"#{pr_artifact.mission_id}" in decoded
        assert "Fix login bug" in decoded

    def test_tears_down_sandbox_on_success(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        create_pr_for_artifact(pr_artifact.id)

        instance.teardown.assert_called_once()

    # --- failure path ---

    def test_writes_create_pr_error_on_failure(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        # Make git push fail
        def failing_exec(cmd, **kwargs):
            joined = " ".join(str(c) for c in cmd)
            if "git push" in joined:
                return MagicMock(exit_code=1, stdout="", stderr="push rejected")
            return MagicMock(exit_code=0, stdout="", stderr="")

        instance.exec.side_effect = failing_exec

        with pytest.raises(RuntimeError, match="git push failed"):
            create_pr_for_artifact(pr_artifact.id)

        pr_artifact.refresh_from_db()
        assert "create_pr_error" in pr_artifact.validation
        assert "git push failed" in pr_artifact.validation["create_pr_error"]

    def test_tears_down_sandbox_on_failure(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        instance.exec.side_effect = RuntimeError("boom")

        with pytest.raises(Exception):
            create_pr_for_artifact(pr_artifact.id)

        instance.teardown.assert_called_once()

    def test_returns_early_when_artifact_missing(self):
        from noctua.runner.tasks import create_pr_for_artifact
        result = create_pr_for_artifact(999_999)
        assert "error" in result

    def test_returns_early_when_no_repo_url(self, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        mission = Mission.objects.create(goal="g", producer_key="pr", repo_url="", budget={})
        artifact = Artifact.objects.create(
            mission=mission, producer_key="pr", kind="pr",
            uri="", preview={}, provenance={}, validation={}, queue_state="pending",
        )
        result = create_pr_for_artifact(artifact.id)
        assert "error" in result
        artifact.refresh_from_db()
        assert "create_pr_error" in artifact.validation

    def test_uses_override_branch_and_title(self, pr_artifact, mock_sandbox):
        from noctua.runner.tasks import create_pr_for_artifact
        _, instance = mock_sandbox

        create_pr_for_artifact(
            pr_artifact.id,
            overrides={"branch": "custom/branch", "title": "My custom title"},
        )

        exec_calls = [" ".join(str(c) for c in ca.args[0]) for ca in instance.exec.call_args_list]
        branch_call = next(s for s in exec_calls if "checkout -b" in s)
        pr_call = next(s for s in exec_calls if "gh pr create" in s)

        assert "custom/branch" in branch_call
        assert "My custom title" in pr_call


# ---------------------------------------------------------------------------
# API endpoint: POST /api/artifacts/:id/create_pr
# ---------------------------------------------------------------------------

class TestCreatePrApiEndpoint:
    def test_returns_200_and_dispatches_task(self, pr_artifact):
        """Endpoint should respond 200 and enqueue the task (mocked delay)."""
        with patch("noctua.runner.tasks.create_pr_for_artifact.delay") as mock_delay:
            c = Client()
            r = c.post(
                f"/api/artifacts/{pr_artifact.id}/create_pr",
                content_type="application/json",
                data="{}",
                **auth(),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == pr_artifact.id
        mock_delay.assert_called_once_with(pr_artifact.id, {})

    def test_returns_404_for_unknown_artifact(self):
        c = Client()
        r = c.post(
            "/api/artifacts/999999/create_pr",
            content_type="application/json",
            data="{}",
            **auth(),
        )
        assert r.status_code == 404

    def test_requires_auth(self, pr_artifact):
        c = Client()
        r = c.post(
            f"/api/artifacts/{pr_artifact.id}/create_pr",
            content_type="application/json",
            data="{}",
        )
        assert r.status_code in (401, 403)

    def test_passes_overrides_to_task(self, pr_artifact):
        with patch("noctua.runner.tasks.create_pr_for_artifact.delay") as mock_delay:
            c = Client()
            r = c.post(
                f"/api/artifacts/{pr_artifact.id}/create_pr",
                content_type="application/json",
                data='{"title": "My PR", "branch": "feat/x"}',
                **auth(),
            )
        assert r.status_code == 200
        _, overrides = mock_delay.call_args.args
        assert overrides["title"] == "My PR"
        assert overrides["branch"] == "feat/x"
