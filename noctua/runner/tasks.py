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
    log_dir = Path(settings.NOCTUA_ARCHIVE_DIR) / str(m.id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / "sandbox.log")
    sandbox = Sandbox(ttl_seconds=m.budget.get("max_wall_seconds", 1800), log_path=log_path)
    try:
        sandbox.boot(image="python:3.12-slim", repo_url=m.repo_url or None)
        plan, tokens = plan_for_mission(m)
        increment_spent(m.id, tokens=tokens)
        producer = get_producer(m.producer_key)
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
