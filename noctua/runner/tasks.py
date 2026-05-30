import json
import shlex
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.utils.timezone import now
from noctua.core.models import Mission, Artifact, Tool
from noctua.sandbox.manager import Sandbox
from noctua.runner.planner import plan_for_mission
from noctua.runner.executor import execute_plan, NeedsInput, StoppedByBudget
from noctua.runner.budget import increment_spent
from noctua.producers.registry import get_producer


@shared_task(time_limit=2000, soft_time_limit=1800)
def run_mission(mission_id: int):
    m = Mission.objects.get(id=mission_id)
    m.state = "running"
    m.started_at = m.started_at or now()
    m.save(update_fields=["state", "started_at"])

    producer = get_producer(m.producer_key)

    # Content-only producers (social, clinical, diagnostic, cad) don't need
    # a sandbox, planner, or executor — they're a single Claude call wrapped
    # in finalize().
    if getattr(producer, "content_only", False):
        try:
            producer.finalize(m, sandbox=None)
            m.state = "succeeded"
        except Exception as e:
            m.state = "failed"
            m.state_reason = f"{type(e).__name__}: {e}"
        finally:
            m.finished_at = now()
            m.save(update_fields=["state", "state_reason", "finished_at"])
            from noctua.runner.archive import archive_mission
            try:
                archive_mission(m.id)
            except Exception:
                pass
        return mission_id

    # External-tools producers (social_post, clinical_analysis, diagnostic, cad after migration):
    # plan + execute, but skip sandbox boot — every tool step is a composio:* call.
    if getattr(producer, "external_tools", False):
        try:
            plan, tokens = plan_for_mission(m, producer=producer)
            increment_spent(m.id, tokens=tokens)
            execute_plan(m, plan, sandbox=None, producer=producer)
            producer.finalize(m, sandbox=None)
            m.state = "succeeded"
        except StoppedByBudget as e:
            m.state = "stopped"
            m.state_reason = f"budget_exceeded: {e.field}"
        except NeedsInput as e:
            m.state = "needs_input"
            m.needs_input_prompt = e.prompt
        except Exception as e:
            m.state = "failed"
            m.state_reason = f"{type(e).__name__}: {e}"
        finally:
            m.finished_at = now()
            m.save(update_fields=["state", "state_reason", "finished_at", "needs_input_prompt"])
            from noctua.runner.archive import archive_mission
            try:
                archive_mission(m.id)
            except Exception:
                pass
        return mission_id

    # ---- existing full lifecycle for PR producer (sandbox + planner + executor) ----
    log_dir = Path(settings.NOCTUA_ARCHIVE_DIR) / str(m.id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / "sandbox.log")
    sandbox = Sandbox(ttl_seconds=m.budget.get("max_wall_seconds", 1800), log_path=log_path, mission_id=m.id)
    try:
        sandbox.boot(image="python:3.12-slim", repo_url=m.repo_url or None)
        plan, tokens = plan_for_mission(m, producer=producer)
        increment_spent(m.id, tokens=tokens)
        try:
            execute_plan(m, plan, sandbox, producer=producer)
        except StoppedByBudget as e:
            m.state = "stopped"
            m.state_reason = f"budget_exceeded: {e.field}"
            m.save(update_fields=["state", "state_reason"])
            return
        except NeedsInput as e:
            m.state = "needs_input"
            m.needs_input_prompt = e.prompt
            m.save(update_fields=["state", "needs_input_prompt"])
            return
        producer.finalize(m, sandbox)
        # also emit kind='tool' artifacts for any tools fabricated during this mission
        for t in Tool.objects.filter(fabricated_by_mission_id=m.id, status="fabricated_sandbox_only"):
            Artifact.objects.get_or_create(
                mission=m, producer_key=m.producer_key, kind="tool", tool=t,
                defaults={
                    "uri": f"file://{t.source_path}",
                    "preview": {"name": t.name, "lines": _count_lines(t.source_path)},
                    "provenance": {},
                    "validation": {"sandbox_only": True},
                    "queue_state": "pending",
                },
            )
        m.state = "succeeded"
    except Exception as e:
        m.state = "failed"
        m.state_reason = f"{type(e).__name__}: {e}"
    finally:
        m.finished_at = now()
        m.save(update_fields=["state", "state_reason", "finished_at"])
        sandbox.teardown()
        from noctua.runner.archive import archive_mission
        try:
            archive_mission(m.id)
        except Exception:
            pass  # archive is best-effort; don't fail the mission on archive error
    return mission_id


def _count_lines(path: str) -> int:
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


_NOCTUA_MD_TEMPLATE = """\
# Noctua review draft

This PR was opened by Noctua for review of artifact #{artifact_id}.

**Mission:** #{mission_id} — {mission_goal}

**Preview**
```
{preview_json}
```

**Validation**
```
{validation_json}
```

> If the mission didn't actually edit any code, this PR is a placeholder
> with just this NOCTUA.md file. Add commits to this branch to fill it in,
> or close the PR if it's not needed.
"""


@shared_task(time_limit=600, soft_time_limit=540)
def create_pr_for_artifact(artifact_id: int, overrides: dict | None = None):
    """Boot a sandbox, push a branch, open a draft PR, and update artifact.uri."""
    overrides = overrides or {}

    # --- look up artifact + mission ---
    try:
        artifact = Artifact.objects.select_related("mission").get(id=artifact_id)
    except Artifact.DoesNotExist:
        return {"error": f"Artifact {artifact_id} not found"}

    mission = artifact.mission
    if mission is None:
        _write_create_pr_error(artifact, "Mission not found for artifact")
        return {"error": "Mission not found"}

    repo_url = mission.repo_url or ""
    if not repo_url:
        msg = "Mission has no repo_url — cannot create a PR"
        _write_create_pr_error(artifact, msg)
        return {"error": msg}

    # --- resolve defaults for branch / title / body / base ---
    branch = overrides.get("branch") or f"noctua/artifact-{artifact_id}"
    preview_title = (artifact.preview or {}).get("title") or f"review for artifact #{artifact_id}"
    title = overrides.get("title") or f"Noctua: {preview_title}"
    base = overrides.get("base") or "main"

    noctua_md = _NOCTUA_MD_TEMPLATE.format(
        artifact_id=artifact_id,
        mission_id=mission.id,
        mission_goal=mission.goal,
        preview_json=json.dumps(artifact.preview, indent=2),
        validation_json=json.dumps(artifact.validation, indent=2),
    )
    body = overrides.get("body") or noctua_md

    # --- boot sandbox ---
    log_dir = Path(settings.NOCTUA_ARCHIVE_DIR) / str(mission.id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / f"create_pr_{artifact_id}.log")
    sandbox = Sandbox(ttl_seconds=540, log_path=log_path, mission_id=mission.id)

    try:
        sandbox.boot(image="python:3.12-slim", repo_url=repo_url)

        # create branch
        r = sandbox.exec(["bash", "-lc", f"cd /work && git checkout -b {shlex.quote(branch)}"])
        if r.exit_code != 0:
            raise RuntimeError(
                f"git checkout -b failed: exit={r.exit_code} "
                f"stdout={r.stdout!r} stderr={r.stderr!r}"
            )

        # write NOCTUA.md and verify the file made it
        sandbox.write_file("/work/NOCTUA.md", noctua_md.encode())
        r = sandbox.exec(["bash", "-lc", "ls -la /work/NOCTUA.md && wc -c /work/NOCTUA.md"])
        if r.exit_code != 0:
            raise RuntimeError(
                f"NOCTUA.md write didn't land: exit={r.exit_code} "
                f"stdout={r.stdout!r} stderr={r.stderr!r}"
            )

        # commit. Use --allow-empty so missing/duplicate NOCTUA.md doesn't
        # block PR creation; the goal is opening the PR, not the diff itself.
        # Capture stdout in the error message — git prints 'nothing to commit'
        # to stdout, not stderr, so the previous error appeared empty.
        commit_msg = shlex.quote(f"noctua: prepare review for artifact #{artifact_id}")
        r = sandbox.exec([
            "bash", "-lc",
            "cd /work && git add -A && "
            f"git -c user.email=noctua@local -c user.name=Noctua commit --allow-empty -m {commit_msg}"
        ])
        if r.exit_code != 0:
            raise RuntimeError(
                f"git commit failed: exit={r.exit_code} "
                f"stdout={r.stdout!r} stderr={r.stderr!r}"
            )

        # push
        r = sandbox.exec(["bash", "-lc", "cd /work && git push -u origin HEAD"])
        if r.exit_code != 0:
            raise RuntimeError(
                f"git push failed: exit={r.exit_code} "
                f"stdout={r.stdout!r} stderr={r.stderr!r}"
            )

        # gh pr create
        t = shlex.quote(title)
        bo = shlex.quote(body)
        ba = shlex.quote(base)
        r = sandbox.exec([
            "bash", "-lc",
            f"cd /work && gh pr create --draft --title {t} --body {bo} --base {ba}"
        ])
        if r.exit_code != 0:
            raise RuntimeError(
                f"gh pr create failed: exit={r.exit_code} "
                f"stdout={r.stdout!r} stderr={r.stderr!r}"
            )

        pr_url = r.stdout.strip()

        # update artifact.uri
        artifact.uri = pr_url
        artifact.save(update_fields=["uri"])

    except Exception as exc:
        _write_create_pr_error(artifact, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        sandbox.teardown()

    return {"artifact_id": artifact_id, "pr_url": pr_url}


def _write_create_pr_error(artifact: Artifact, message: str) -> None:
    """Best-effort: record the failure in artifact.validation so the UI can surface it."""
    try:
        validation = dict(artifact.validation or {})
        validation["create_pr_error"] = message
        artifact.validation = validation
        artifact.save(update_fields=["validation"])
    except Exception:
        pass
