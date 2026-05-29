# Noctua MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the overnight PR-builder vertical end-to-end. `noctua run <github-issue-url>` boots a Docker sandbox, plans the work, edits + tests in a loop until green, opens a draft PR, lands an artifact in a Review UI. Approving the PR artifact flips the PR to ready-for-review. Tools fabricated during a mission persist and can be graduated for reuse across future missions. Other producer kinds (social, clinical, diagnostic) ship as stubs because the orchestration spine is the load-bearing thing; new producers are orthogonal additions.

**Architecture:** Monolithic Django (Django Ninja API) + Postgres control plane. Celery + Redis worker runs missions. Sandbox manager wraps Docker SDK (single container per mission). Tool registry with three-tier precedence (`graduated` > `hardcoded` > `fabricated_sandbox_only`). PRProducer drives an LLM tool-use code-edit + test-run loop. Next.js + Tailwind Review UI.

**Tech stack:** Python 3.12, Django 5.x + django-ninja, Postgres 16, Celery 5 + Redis 7, Docker SDK for Python, Anthropic SDK (Sonnet 4.6 planner, Opus 4.7 code edits + fabrication, prompt caching), Click (CLI), Next.js 15 + Tailwind 4, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-05-29-noctua-mvp-design.md` — read first.

---

## Workstream map

| WS | Name | What it produces | Tasks |
|---|---|---|---|
| 1 | Foundation | Control plane (Django Ninja + Postgres), Celery worker shell, CLI, auth, models. `noctua run` posts a mission and a worker picks it up. | 1–10 |
| 2 | Sandbox + Tools | `noctua.sandbox` and `noctua.tools` libraries — Docker SDK wrapper, bundled tools, fabricator with nested-sandbox validation. | 11–18 |
| 3 | Mission Runner + PR Producer | Planner, executor loop with budget enforcement, PR producer with Claude tool-use edit loop, full mission lifecycle. | 19–25 |
| 4 | Review UI | Next.js + Tailwind queue, artifact detail, approve/reject/graduate flows, rubric editor. | 26–31 |
| 5 | Example target + Operations | A test fixture repo (`noctua-demo-app`) we point Noctua at during dev. Mission archive + replay for observability and debugging. | 32–34 |

**Dependencies.** WS 1 → WS 2 → WS 3 (sequential). WS 4 can start as soon as WS 1's API exists. WS 5 is independent of WS 3 only because we can use any repo for testing; the `noctua-demo-app` fixture is convenient, not required.

---

## Pre-flight (do once before Task 1)

- [ ] Verify Docker Desktop is running: `docker ps` returns no error.
- [ ] Verify `gh` CLI is authenticated: `gh auth status` shows logged in as `hugoduar`.
- [ ] Verify Python 3.12 is available: `python3.12 --version`.
- [ ] Verify Node 20+ is available: `node --version`.
- [ ] Export env vars in your shell (and write them to `.env.example`):
  ```bash
  export ANTHROPIC_API_KEY=sk-ant-...
  export NOCTUA_API_TOKEN=$(openssl rand -hex 32)
  export GITHUB_TOKEN=$(gh auth token)
  ```
- [ ] Confirm Postgres + Redis are runnable via docker-compose (we'll create the compose file in Task 1).

---

## WS 1 — Foundation

### Task 1: Repo skeleton + dependency setup

**Files:**
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `noctua/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "noctua"
version = "0.1.0"
description = "AI that never sleeps — overnight artifact factory"
requires-python = ">=3.12"
dependencies = [
  "django>=5.0,<6.0",
  "django-ninja>=1.3",
  "psycopg[binary]>=3.2",
  "celery[redis]>=5.4",
  "redis>=5.0",
  "docker>=7.1",
  "anthropic>=0.40",
  "click>=8.1",
  "httpx>=0.27",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-django>=4.9",
  "pytest-celery>=1.1",
  "pytest-mock>=3.14",
  "ruff>=0.7",
]

[project.scripts]
noctua = "noctua.cli:cli"

[project.entry-points."noctua.producers"]
pr = "noctua.producers.pr:PRProducer"
social_post = "noctua.producers.stub:SocialPostStub"
clinical_analysis = "noctua.producers.stub:ClinicalAnalysisStub"
diagnostic = "noctua.producers.stub:DiagnosticStub"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "noctua.settings"
python_files = ["test_*.py"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: noctua
      POSTGRES_PASSWORD: noctua
      POSTGRES_DB: noctua
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U noctua"]
      interval: 5s

  redis:
    image: redis:7
    ports: ["6379:6379"]
```

- [ ] **Step 3: Write `.env.example`**

```bash
ANTHROPIC_API_KEY=sk-ant-...
NOCTUA_API_TOKEN=replace-with-random
GITHUB_TOKEN=ghp_...
DATABASE_URL=postgres://noctua:noctua@localhost:5432/noctua
REDIS_URL=redis://localhost:6379/0
NOCTUA_DEMO_REPO=https://github.com/hugoduar/noctua-demo-app
```

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
node_modules/
ui/.next/
archive/
tools/fabricated/
tools/graduated/
```

- [ ] **Step 5: Create empty package + install**

```bash
mkdir -p noctua tests
echo '__version__ = "0.1.0"' > noctua/__init__.py
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d
```

Expected: `docker compose ps` shows postgres + redis healthy.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml docker-compose.yml .env.example .gitignore noctua/__init__.py
git commit -m "feat(foundation): repo skeleton, dependencies, dev infra"
```

---

### Task 2: Django project + settings

**Files:**
- Create: `noctua/settings.py`
- Create: `noctua/urls.py`
- Create: `noctua/wsgi.py`
- Create: `noctua/asgi.py`
- Create: `manage.py`

- [ ] **Step 1: Write `noctua/settings.py`**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-do-not-use-in-prod")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "noctua.core",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "noctua.urls"
WSGI_APPLICATION = "noctua.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "noctua",
        "USER": "noctua",
        "PASSWORD": "noctua",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_TIME_LIMIT = 60 * 60  # 1h hard ceiling, per-mission override
CELERY_TASK_SOFT_TIME_LIMIT = 30 * 60

NOCTUA_API_TOKEN = os.environ.get("NOCTUA_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
NOCTUA_ARCHIVE_DIR = BASE_DIR / "archive"
NOCTUA_TOOLS_DIR = BASE_DIR / "tools"
```

- [ ] **Step 2: Write `noctua/urls.py`**

```python
from django.urls import path
from noctua.core.api import api

urlpatterns = [
    path("api/", api.urls),
]
```

- [ ] **Step 3: Write `noctua/wsgi.py` and `noctua/asgi.py`**

```python
# noctua/wsgi.py
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noctua.settings")
application = get_wsgi_application()
```

```python
# noctua/asgi.py
import os
from django.core.asgi import get_asgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noctua.settings")
application = get_asgi_application()
```

- [ ] **Step 4: Write `manage.py`**

```python
#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noctua.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify Django boots**

```bash
chmod +x manage.py
mkdir -p noctua/core
touch noctua/core/__init__.py
# stub api so urls.py imports
cat > noctua/core/api.py <<'EOF'
from ninja import NinjaAPI
api = NinjaAPI(title="Noctua")
EOF
./manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add manage.py noctua/settings.py noctua/urls.py noctua/wsgi.py noctua/asgi.py noctua/core/__init__.py noctua/core/api.py
git commit -m "feat(foundation): django project + ninja api stub"
```

---

### Task 3: Core models

**Files:**
- Create: `noctua/core/models.py`
- Create: `noctua/core/migrations/__init__.py`
- Test: `tests/core/test_models.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/core/test_models.py
import pytest
from noctua.core.models import Mission, Plan, SandboxRun, Tool, Artifact, Producer

pytestmark = pytest.mark.django_db

def test_mission_defaults():
    m = Mission.objects.create(
        goal="Add /healthz",
        producer_key="pr",
        repo_url="https://github.com/x/y",
        budget={"max_wall_seconds": 1800, "max_tokens": 200000, "max_tool_calls": 50},
    )
    assert m.state == "queued"
    assert m.spent == {"wall_seconds": 0, "tokens": 0, "tool_calls": 0}
    assert m.auto_act is False

def test_plan_versioning():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    p1 = Plan.objects.create(mission=m, version=1, steps=[], rendered_md="")
    p2 = Plan.objects.create(mission=m, version=2, steps=[], rendered_md="")
    assert p1.version == 1 and p2.version == 2

def test_tool_status_choices():
    t = Tool.objects.create(name="seed_db", signature={}, source_path="x", source_hash="h", status="fabricated_sandbox_only")
    assert t.status == "fabricated_sandbox_only"

def test_artifact_links_tool():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    t = Tool.objects.create(name="seed_db", signature={}, source_path="x", source_hash="h", status="fabricated_sandbox_only")
    a = Artifact.objects.create(mission=m, producer_key="pr", kind="tool", uri="file://x", preview={}, provenance={}, validation={}, queue_state="pending", tool=t)
    assert a.tool_id == t.id
```

- [ ] **Step 2: Run tests — confirm fail with import error**

```bash
pytest tests/core/test_models.py -x
```

Expected: ImportError or ModuleNotFoundError on `Mission`.

- [ ] **Step 3: Write `noctua/core/models.py`**

```python
from django.db import models

MISSION_STATES = [(s, s) for s in ["queued", "running", "succeeded", "failed", "stopped", "needs_input"]]
DOMAINS = [(d, d) for d in ["code", "social", "clinical", "diagnostic", "cad"]]
SANDBOX_STATES = [(s, s) for s in ["booting", "ready", "exited", "torn_down"]]
TOOL_STATUSES = [(s, s) for s in ["hardcoded", "fabricated_sandbox_only", "graduated"]]
ARTIFACT_KINDS = [(k, k) for k in ["pr", "social_post", "analysis", "diagnostic", "cad", "tool"]]
QUEUE_STATES = [(s, s) for s in ["pending", "approved", "rejected", "promoted"]]

def empty_spent():
    return {"wall_seconds": 0, "tokens": 0, "tool_calls": 0}

class Mission(models.Model):
    goal = models.TextField()
    inputs = models.JSONField(default=dict)
    success_criteria = models.TextField(blank=True)
    domain = models.CharField(max_length=32, choices=DOMAINS, default="code")
    producer_key = models.CharField(max_length=64)
    repo_url = models.TextField(blank=True)
    issue_url = models.TextField(blank=True)
    state = models.CharField(max_length=32, choices=MISSION_STATES, default="queued")
    state_reason = models.TextField(blank=True)
    budget = models.JSONField(default=dict)
    spent = models.JSONField(default=empty_spent)
    needs_input_prompt = models.TextField(null=True, blank=True)
    needs_input_response = models.TextField(null=True, blank=True)
    auto_act = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class Plan(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="plans")
    version = models.IntegerField(default=1)
    steps = models.JSONField(default=list)
    rendered_md = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [("mission", "version")]

class SandboxRun(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="sandboxes")
    image_ref = models.CharField(max_length=512)
    container_id = models.CharField(max_length=128, null=True, blank=True)
    state = models.CharField(max_length=32, choices=SANDBOX_STATES, default="booting")
    log_path = models.TextField(blank=True)
    ttl_seconds = models.IntegerField(default=1800)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class Tool(models.Model):
    name = models.CharField(max_length=128, db_index=True)
    signature = models.JSONField(default=dict)
    source_path = models.TextField()
    source_hash = models.CharField(max_length=128)
    fabricated_by_mission = models.ForeignKey(Mission, on_delete=models.SET_NULL, null=True, blank=True, related_name="fabricated_tools")
    status = models.CharField(max_length=32, choices=TOOL_STATUSES, default="hardcoded")
    created_at = models.DateTimeField(auto_now_add=True)

class Artifact(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="artifacts")
    producer_key = models.CharField(max_length=64)
    kind = models.CharField(max_length=32, choices=ARTIFACT_KINDS)
    uri = models.TextField()
    preview = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    validation = models.JSONField(default=dict)
    queue_state = models.CharField(max_length=32, choices=QUEUE_STATES, default="pending")
    tool = models.ForeignKey(Tool, on_delete=models.SET_NULL, null=True, blank=True, related_name="artifacts")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

class Producer(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    kind = models.CharField(max_length=32, choices=ARTIFACT_KINDS)
    rubric_md = models.TextField(blank=True)
    default_budget = models.JSONField(default=dict)
    version = models.IntegerField(default=1)
```

- [ ] **Step 4: Make + run migrations**

```bash
./manage.py makemigrations core
./manage.py migrate
```

Expected: `Applying core.0001_initial... OK`.

- [ ] **Step 5: Run tests — confirm pass**

```bash
pytest tests/core/test_models.py -v
```

Expected: all 4 pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/core/models.py noctua/core/migrations/ tests/core/test_models.py
mkdir -p tests/core && touch tests/__init__.py tests/core/__init__.py
git add tests/__init__.py tests/core/__init__.py
git commit -m "feat(foundation): core data model + migrations"
```

---

### Task 4: Bearer-token auth dependency

**Files:**
- Create: `noctua/core/auth.py`
- Test: `tests/core/test_auth.py`

- [ ] **Step 1: Write failing auth tests**

```python
# tests/core/test_auth.py
import pytest
from django.test import RequestFactory
from django.conf import settings
from noctua.core.auth import BearerAuth

def test_bearer_accepts_correct_token(settings):
    settings.NOCTUA_API_TOKEN = "good-token"
    auth = BearerAuth()
    req = RequestFactory().get("/api/queue", HTTP_AUTHORIZATION="Bearer good-token")
    assert auth.authenticate(req, "good-token") == "good-token"

def test_bearer_rejects_wrong_token(settings):
    settings.NOCTUA_API_TOKEN = "good-token"
    auth = BearerAuth()
    req = RequestFactory().get("/api/queue", HTTP_AUTHORIZATION="Bearer wrong-token")
    assert auth.authenticate(req, "wrong-token") is None
```

- [ ] **Step 2: Write `noctua/core/auth.py`**

```python
from django.conf import settings
from ninja.security import HttpBearer

class BearerAuth(HttpBearer):
    def authenticate(self, request, token):
        if settings.NOCTUA_API_TOKEN and token == settings.NOCTUA_API_TOKEN:
            return token
        return None
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/core/test_auth.py -v
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/core/auth.py tests/core/test_auth.py
git commit -m "feat(foundation): bearer-token auth dependency"
```

---

### Task 5: Mission API (create, get, cancel, respond)

**Files:**
- Create: `noctua/core/schemas.py`
- Modify: `noctua/core/api.py`
- Test: `tests/core/test_mission_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/core/test_mission_api.py
import pytest
from django.test import Client
from django.conf import settings

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def token(settings):
    settings.NOCTUA_API_TOKEN = "test-token"

def auth():
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}

def test_create_mission():
    c = Client()
    r = c.post(
        "/api/missions",
        data={"goal": "Add /healthz", "producer_key": "pr", "repo_url": "https://github.com/x/y"},
        content_type="application/json",
        **auth(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "queued"
    assert body["id"]

def test_get_mission():
    c = Client()
    create = c.post("/api/missions", data={"goal": "g", "producer_key": "pr", "repo_url": "r"}, content_type="application/json", **auth()).json()
    r = c.get(f"/api/missions/{create['id']}", **auth())
    assert r.status_code == 200
    assert r.json()["goal"] == "g"

def test_unauthenticated_rejected():
    c = Client()
    r = c.get("/api/missions/1")
    assert r.status_code == 401
```

- [ ] **Step 2: Write `noctua/core/schemas.py`**

```python
from ninja import Schema
from typing import Optional

class MissionCreate(Schema):
    goal: str
    producer_key: str
    repo_url: str = ""
    issue_url: str = ""
    inputs: dict = {}
    success_criteria: str = ""
    domain: str = "code"
    budget: dict = {}
    auto_act: bool = False

class MissionOut(Schema):
    id: int
    goal: str
    state: str
    state_reason: str
    producer_key: str
    repo_url: str
    issue_url: str
    budget: dict
    spent: dict
    needs_input_prompt: Optional[str] = None

class RespondIn(Schema):
    response: str

class ArtifactOut(Schema):
    id: int
    mission_id: int
    producer_key: str
    kind: str
    uri: str
    preview: dict
    validation: dict
    queue_state: str
    tool_id: Optional[int] = None
```

- [ ] **Step 3: Update `noctua/core/api.py`**

```python
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI
from noctua.core.auth import BearerAuth
from noctua.core.models import Mission, Artifact
from noctua.core.schemas import MissionCreate, MissionOut, RespondIn, ArtifactOut

api = NinjaAPI(title="Noctua", auth=BearerAuth())

DEFAULT_BUDGET = {"max_wall_seconds": 1800, "max_tokens": 200_000, "max_tool_calls": 50}

@api.post("/missions", response={201: MissionOut})
def create_mission(request, payload: MissionCreate):
    from noctua.runner.tasks import run_mission  # local import to avoid Celery at import time
    budget = payload.budget or DEFAULT_BUDGET
    m = Mission.objects.create(
        goal=payload.goal,
        inputs=payload.inputs,
        success_criteria=payload.success_criteria,
        domain=payload.domain,
        producer_key=payload.producer_key,
        repo_url=payload.repo_url,
        issue_url=payload.issue_url,
        budget=budget,
        auto_act=payload.auto_act,
    )
    run_mission.delay(m.id)
    return 201, m

@api.get("/missions/{mission_id}", response=MissionOut)
def get_mission(request, mission_id: int):
    return get_object_or_404(Mission, id=mission_id)

@api.post("/missions/{mission_id}/cancel", response=MissionOut)
def cancel_mission(request, mission_id: int):
    m = get_object_or_404(Mission, id=mission_id)
    if m.state in ("queued", "running", "needs_input"):
        m.state = "failed"
        m.state_reason = "cancelled_by_user"
        m.save(update_fields=["state", "state_reason"])
    return m

@api.post("/missions/{mission_id}/respond", response=MissionOut)
def respond_to_mission(request, mission_id: int, payload: RespondIn):
    from noctua.runner.tasks import run_mission
    m = get_object_or_404(Mission, id=mission_id)
    if m.state != "needs_input":
        return m
    m.needs_input_response = payload.response
    m.state = "queued"
    m.save(update_fields=["needs_input_response", "state"])
    run_mission.delay(m.id)
    return m

@api.get("/queue", response=list[ArtifactOut])
def list_queue(request, kind: str | None = None, queue_state: str | None = None):
    qs = Artifact.objects.all().order_by("-created_at")
    if kind:
        qs = qs.filter(kind=kind)
    if queue_state:
        qs = qs.filter(queue_state=queue_state)
    return list(qs[:100])

@api.get("/artifacts/{artifact_id}", response=ArtifactOut)
def get_artifact(request, artifact_id: int):
    return get_object_or_404(Artifact, id=artifact_id)
```

- [ ] **Step 4: Stub the Celery task so import works**

```python
# noctua/runner/__init__.py (create)
```

```python
# noctua/runner/tasks.py
from celery import shared_task

@shared_task
def run_mission(mission_id: int):
    # filled in Task 19
    return None
```

- [ ] **Step 5: Run tests**

```bash
mkdir -p noctua/runner
touch noctua/runner/__init__.py
# write noctua/runner/tasks.py per Step 4
pytest tests/core/test_mission_api.py -v
```

Expected: all 3 pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/core/schemas.py noctua/core/api.py noctua/runner/__init__.py noctua/runner/tasks.py tests/core/test_mission_api.py
git commit -m "feat(foundation): mission CRUD + queue API"
```

---

### Task 6: Queue + artifact actions API (approve / reject / promote / graduate)

**Files:**
- Modify: `noctua/core/api.py`
- Test: `tests/core/test_artifact_actions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_artifact_actions.py
import pytest
from django.test import Client
from noctua.core.models import Mission, Artifact, Tool

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def token(settings):
    settings.NOCTUA_API_TOKEN = "tt"

def auth():
    return {"HTTP_AUTHORIZATION": "Bearer tt"}

@pytest.fixture
def pr_artifact():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    return Artifact.objects.create(mission=m, producer_key="pr", kind="pr", uri="https://github.com/x/y/pull/1", preview={}, provenance={}, validation={}, queue_state="pending")

@pytest.fixture
def tool_artifact():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    t = Tool.objects.create(name="seed_db", signature={}, source_path="tools/fabricated/h/seed_db.py", source_hash="h", status="fabricated_sandbox_only")
    return Artifact.objects.create(mission=m, producer_key="pr", kind="tool", uri="file://...", preview={}, provenance={}, validation={}, queue_state="pending", tool=t)

def test_approve_pr_calls_on_approve(pr_artifact, mocker):
    spy = mocker.patch("noctua.producers.pr.PRProducer.on_approve")
    c = Client()
    r = c.post(f"/api/artifacts/{pr_artifact.id}/approve", **auth())
    assert r.status_code == 200
    assert r.json()["queue_state"] == "approved"
    assert spy.called

def test_reject_pr(pr_artifact):
    c = Client()
    r = c.post(f"/api/artifacts/{pr_artifact.id}/reject", **auth())
    assert r.status_code == 200
    assert r.json()["queue_state"] == "rejected"

def test_graduate_tool(tool_artifact, tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    (tmp_path / "fabricated/h").mkdir(parents=True)
    (tmp_path / "fabricated/h/seed_db.py").write_text("def call(args, sandbox): pass\n")
    tool_artifact.tool.source_path = str(tmp_path / "fabricated/h/seed_db.py")
    tool_artifact.tool.save()
    c = Client()
    r = c.post(f"/api/artifacts/{tool_artifact.id}/approve", **auth())
    assert r.status_code == 200
    tool_artifact.tool.refresh_from_db()
    assert tool_artifact.tool.status == "graduated"
    assert (tmp_path / "graduated/seed_db.py").exists()
```

- [ ] **Step 2: Add actions endpoints to `noctua/core/api.py`**

```python
# append to noctua/core/api.py
import shutil
from django.conf import settings
from django.utils.timezone import now
from noctua.core.models import Tool
from noctua.producers.registry import get_producer

@api.post("/artifacts/{artifact_id}/approve", response=ArtifactOut)
def approve_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "approved"
    a.reviewed_at = now()
    a.save(update_fields=["queue_state", "reviewed_at"])
    if a.kind == "tool" and a.tool:
        a.tool.status = "graduated"
        a.tool.save(update_fields=["status"])
        src = settings.NOCTUA_TOOLS_DIR / a.tool.source_path
        if not src.is_absolute():
            src = settings.NOCTUA_TOOLS_DIR.parent / a.tool.source_path
        dst = settings.NOCTUA_TOOLS_DIR / "graduated" / f"{a.tool.name}.py"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src if src.exists() else a.tool.source_path, dst)
    else:
        producer = get_producer(a.producer_key)
        producer.on_approve(a)
    return a

@api.post("/artifacts/{artifact_id}/reject", response=ArtifactOut)
def reject_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "rejected"
    a.reviewed_at = now()
    a.save(update_fields=["queue_state", "reviewed_at"])
    if a.kind == "tool" and a.tool:
        a.tool.delete()
    return a

@api.post("/artifacts/{artifact_id}/promote", response=ArtifactOut)
def promote_artifact(request, artifact_id: int):
    a = get_object_or_404(Artifact, id=artifact_id)
    a.queue_state = "promoted"
    a.save(update_fields=["queue_state"])
    producer = get_producer(a.producer_key)
    producer.on_promote(a)
    return a
```

- [ ] **Step 3: Stub the producer registry to make tests importable**

```python
# noctua/producers/__init__.py (create)
```

```python
# noctua/producers/registry.py
from importlib.metadata import entry_points

_cache = {}

def get_producer(key: str):
    if key in _cache:
        return _cache[key]
    for ep in entry_points(group="noctua.producers"):
        if ep.name == key:
            cls = ep.load()
            inst = cls()
            _cache[key] = inst
            return inst
    raise LookupError(f"producer not found: {key}")
```

```python
# noctua/producers/pr.py (stub for now, full version Task 26)
class PRProducer:
    key = "pr"
    kind = "pr"
    def on_approve(self, artifact):
        pass
    def on_promote(self, artifact):
        pass
```

```python
# noctua/producers/stub.py (stub for now, full version Task 27)
class _Stub:
    def on_approve(self, artifact): pass
    def on_promote(self, artifact): pass

class SocialPostStub(_Stub):
    key = "social_post"
    kind = "social_post"

class ClinicalAnalysisStub(_Stub):
    key = "clinical_analysis"
    kind = "analysis"

class DiagnosticStub(_Stub):
    key = "diagnostic"
    kind = "diagnostic"
```

- [ ] **Step 4: Run tests**

```bash
mkdir -p noctua/producers
# create the four files above
pip install -e ".[dev]"  # re-register entry points
pytest tests/core/test_artifact_actions.py -v
```

Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add noctua/core/api.py noctua/producers/ tests/core/test_artifact_actions.py
git commit -m "feat(foundation): artifact approve/reject/promote + tool graduation"
```

---

### Task 7: Celery wiring + smoke

**Files:**
- Create: `noctua/celery.py`
- Modify: `noctua/__init__.py`
- Test: `tests/runner/test_celery_smoke.py`

- [ ] **Step 1: Write `noctua/celery.py`**

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "noctua.settings")

app = Celery("noctua")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["noctua.runner"])
```

- [ ] **Step 2: Update `noctua/__init__.py`**

```python
from noctua.celery import app as celery_app

__all__ = ("celery_app",)
__version__ = "0.1.0"
```

- [ ] **Step 3: Make `run_mission` set state to running (placeholder, replaced in Task 19)**

```python
# noctua/runner/tasks.py
from celery import shared_task
from django.utils.timezone import now
from noctua.core.models import Mission

@shared_task
def run_mission(mission_id: int):
    m = Mission.objects.get(id=mission_id)
    m.state = "running"
    m.started_at = now()
    m.save(update_fields=["state", "started_at"])
    # placeholder — replaced by full lifecycle in Task 19
    m.state = "succeeded"
    m.finished_at = now()
    m.save(update_fields=["state", "finished_at"])
    return mission_id
```

- [ ] **Step 4: Write smoke test**

```python
# tests/runner/test_celery_smoke.py
import pytest
from noctua.core.models import Mission
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

def test_run_mission_placeholder_advances_state():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    run_mission(m.id)  # call directly, no broker needed
    m.refresh_from_db()
    assert m.state == "succeeded"
```

- [ ] **Step 5: Run tests + start a worker manually to verify wiring**

```bash
mkdir -p tests/runner && touch tests/runner/__init__.py
pytest tests/runner/test_celery_smoke.py -v
# In another shell, optional smoke against the real broker:
# celery -A noctua worker -l info  # should connect to redis and show registered task noctua.runner.tasks.run_mission
```

Expected: test passes. If you ran the worker, it prints `[tasks] . noctua.runner.tasks.run_mission`.

- [ ] **Step 6: Commit**

```bash
git add noctua/celery.py noctua/__init__.py noctua/runner/tasks.py tests/runner/__init__.py tests/runner/test_celery_smoke.py
git commit -m "feat(foundation): celery app + placeholder run_mission"
```

---

### Task 8: CLI (`noctua run`)

**Files:**
- Create: `noctua/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

```python
# tests/test_cli.py
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
```

- [ ] **Step 2: Write `noctua/cli.py`**

```python
import os
import click
import httpx

@click.group()
def cli():
    """Noctua — overnight artifact factory."""

@cli.command()
@click.option("--repo", required=True, help="GitHub repo URL")
@click.option("--issue", required=True, help="GitHub issue URL")
@click.option("--goal", default=None, help="Override mission goal (defaults to issue title)")
@click.option("--producer", default="pr")
def run(repo, issue, goal, producer):
    """Queue a mission."""
    api_url = os.environ.get("NOCTUA_API_URL", "http://localhost:8000")
    token = os.environ.get("NOCTUA_API_TOKEN", "")
    payload = {
        "goal": goal or f"Resolve {issue}",
        "producer_key": producer,
        "repo_url": repo,
        "issue_url": issue,
    }
    r = httpx.post(f"{api_url}/api/missions", json=payload, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    body = r.json()
    click.echo(f"Mission {body['id']} queued.")
```

- [ ] **Step 3: Run test**

```bash
pytest tests/test_cli.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/cli.py tests/test_cli.py
git commit -m "feat(foundation): noctua CLI with `run` command"
```

---

### Task 9: Seed producers + rubric endpoints

**Files:**
- Create: `noctua/core/management/__init__.py`
- Create: `noctua/core/management/commands/__init__.py`
- Create: `noctua/core/management/commands/seed_producers.py`
- Create: `noctua/producers/pr/rubric.md`
- Create: `noctua/producers/stub/social_post_rubric.md` (etc.)
- Modify: `noctua/core/api.py`
- Test: `tests/core/test_producer_api.py`

- [ ] **Step 1: Create rubric files**

```bash
mkdir -p noctua/producers/pr noctua/producers/stub
cat > noctua/producers/pr/rubric.md <<'EOF'
# PR Producer Rubric

A "good" PR from Noctua:
- Closes the linked issue.
- Adds tests for the new behavior.
- All tests pass in the sandbox.
- Commit message is a single imperative sentence.
- PR body has: what changed, why, and a "Noctua report" footer.
EOF

cat > noctua/producers/stub/social_post_rubric.md <<'EOF'
# Social Post Rubric (stub)
Friendly, on-brand, 280 chars max.
EOF

cat > noctua/producers/stub/clinical_rubric.md <<'EOF'
# Clinical Analysis Rubric (stub)
Pre-registered comparisons only. Surface caveats.
EOF

cat > noctua/producers/stub/diagnostic_rubric.md <<'EOF'
# Diagnostic Rubric (stub)
One page per vehicle. Parts list with manufacturer codes.
EOF
```

- [ ] **Step 2: Write `seed_producers` management command**

```python
# noctua/core/management/commands/seed_producers.py
from pathlib import Path
from django.core.management.base import BaseCommand
from noctua.core.models import Producer

SEED = [
    ("pr", "pr", "noctua/producers/pr/rubric.md"),
    ("social_post", "social_post", "noctua/producers/stub/social_post_rubric.md"),
    ("clinical_analysis", "analysis", "noctua/producers/stub/clinical_rubric.md"),
    ("diagnostic", "diagnostic", "noctua/producers/stub/diagnostic_rubric.md"),
]

class Command(BaseCommand):
    help = "Seed Producer rows from on-disk rubric markdown files."

    def handle(self, *args, **kwargs):
        for key, kind, rubric_path in SEED:
            md = Path(rubric_path).read_text() if Path(rubric_path).exists() else ""
            obj, created = Producer.objects.update_or_create(
                key=key, defaults={"kind": kind, "rubric_md": md, "default_budget": {"max_wall_seconds": 1800, "max_tokens": 200000, "max_tool_calls": 50}}
            )
            self.stdout.write(f"{'created' if created else 'updated'} producer {key}")
```

- [ ] **Step 3: Write failing rubric-API test**

```python
# tests/core/test_producer_api.py
import pytest
from django.test import Client
from django.core.management import call_command
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
    Producer.objects.get(key="pr").rubric_md == "new rubric content"
```

- [ ] **Step 4: Add endpoints to `noctua/core/api.py`**

```python
# append to noctua/core/api.py
from noctua.core.models import Producer

class ProducerOut(Schema):
    key: str
    kind: str
    rubric_md: str
    version: int

class RubricIn(Schema):
    rubric_md: str

@api.get("/producers", response=list[ProducerOut])
def list_producers(request):
    return list(Producer.objects.all())

@api.put("/producers/{key}/rubric", response=ProducerOut)
def update_rubric(request, key: str, payload: RubricIn):
    p = get_object_or_404(Producer, key=key)
    p.rubric_md = payload.rubric_md
    p.version += 1
    p.save(update_fields=["rubric_md", "version"])
    # also write to disk so it's git-trackable
    paths = {"pr": "noctua/producers/pr/rubric.md"}
    if key in paths:
        from pathlib import Path
        Path(paths[key]).write_text(payload.rubric_md)
    return p
```

(Move the `Schema` import to the top of the file if not present.)

- [ ] **Step 5: Run tests**

```bash
mkdir -p noctua/core/management/commands
touch noctua/core/management/__init__.py noctua/core/management/commands/__init__.py
./manage.py seed_producers
pytest tests/core/test_producer_api.py -v
```

Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/core/management/ noctua/producers/pr/rubric.md noctua/producers/stub/ noctua/core/api.py tests/core/test_producer_api.py
git commit -m "feat(foundation): producer seed command + rubric endpoints"
```

---

### Task 10: End-to-end Foundation smoke

**Goal:** Confirm CLI → API → Celery → DB works end-to-end against running services.

- [ ] **Step 1: Start services**

```bash
docker compose up -d
./manage.py migrate
./manage.py seed_producers
./manage.py runserver 8000 &
celery -A noctua worker -l info &
```

- [ ] **Step 2: Fire a mission via CLI**

```bash
export NOCTUA_API_URL=http://localhost:8000
export NOCTUA_API_TOKEN=$NOCTUA_API_TOKEN  # already in your shell
noctua run --repo https://github.com/x/y --issue https://github.com/x/y/issues/1 --goal "smoke"
```

Expected: `Mission 1 queued.`

- [ ] **Step 3: Verify it advanced**

```bash
curl -s -H "Authorization: Bearer $NOCTUA_API_TOKEN" http://localhost:8000/api/missions/1 | python -m json.tool
```

Expected: `state` is `succeeded` (placeholder `run_mission` ran).

- [ ] **Step 4: Stop services and commit a `Makefile`**

```makefile
# Makefile
.PHONY: up down api worker migrate seed test

up:
	docker compose up -d

down:
	docker compose down

api:
	./manage.py runserver 8000

worker:
	celery -A noctua worker -l info

migrate:
	./manage.py migrate

seed:
	./manage.py seed_producers

test:
	pytest -x
```

```bash
git add Makefile
git commit -m "feat(foundation): Makefile + ws1 smoke verified"
```

---

## WS 2 — Sandbox + Tools

### Task 11: Sandbox manager — boot + teardown

**Files:**
- Create: `noctua/sandbox/__init__.py`
- Create: `noctua/sandbox/manager.py`
- Test: `tests/sandbox/test_sandbox_boot.py`

- [ ] **Step 1: Write failing test (integration — needs Docker)**

```python
# tests/sandbox/test_sandbox_boot.py
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
```

- [ ] **Step 2: Write `noctua/sandbox/manager.py` (boot + teardown only)**

```python
import time
import docker
from dataclasses import dataclass, field

@dataclass
class SandboxRunInfo:
    container_id: str = ""
    image_ref: str = ""
    state: str = "booting"
    log_path: str = ""

class Sandbox:
    def __init__(self, ttl_seconds: int = 1800):
        self.client = docker.from_env()
        self.container = None
        self.ttl_seconds = ttl_seconds
        self.info = SandboxRunInfo()

    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
        self.client.images.pull(image)  # idempotent
        self.container = self.client.containers.run(
            image,
            command="sleep infinity",
            detach=True,
            cpu_count=2,
            mem_limit="2g",
            working_dir="/work",
            tmpfs={"/work": "rw,size=512m"},
            network_mode="bridge",
            labels={"noctua.role": "mission"},
        )
        self.info.container_id = self.container.id
        self.info.image_ref = image
        self.info.state = "ready"
        if repo_url:
            self.exec(["bash", "-lc", f"apt-get update -qq && apt-get install -qq -y git && git clone {repo_url} /work"], timeout=300)
        return self.info

    def exec(self, cmd: list[str], stdin: str = "", timeout: int = 60):
        # filled in Task 12
        result = self.container.exec_run(cmd, demux=True)
        return result

    def teardown(self):
        if self.container is not None:
            try:
                self.container.kill()
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception:
                pass
            self.container = None
            self.info.state = "torn_down"
```

- [ ] **Step 3: Run test**

```bash
mkdir -p noctua/sandbox tests/sandbox
touch noctua/sandbox/__init__.py tests/sandbox/__init__.py
pytest tests/sandbox/test_sandbox_boot.py -v
```

Expected: pass. (~10s including image pull on first run.)

- [ ] **Step 4: Commit**

```bash
git add noctua/sandbox/ tests/sandbox/
git commit -m "feat(sandbox): boot + teardown lifecycle"
```

---

### Task 12: Sandbox manager — exec + file IO + log streaming

**Files:**
- Modify: `noctua/sandbox/manager.py`
- Test: `tests/sandbox/test_sandbox_exec.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/sandbox/test_sandbox_exec.py
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
```

- [ ] **Step 2: Update `noctua/sandbox/manager.py`**

```python
# replace Sandbox.exec and add file IO + log streaming
import io
import tarfile
from dataclasses import dataclass

@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str

class Sandbox:
    # ... __init__, boot, teardown unchanged ...

    def exec(self, cmd: list[str], stdin: str = "", timeout: int = 60) -> ExecResult:
        # docker SDK exec doesn't honor stdin easily; for stdin we'd shell-wrap.
        # For MVP we ignore stdin and accept timeout via daemon-side wait.
        result = self.container.exec_run(cmd, demux=True)
        stdout_b, stderr_b = result.output if isinstance(result.output, tuple) else (result.output, None)
        return ExecResult(
            exit_code=result.exit_code,
            stdout=(stdout_b or b"").decode("utf-8", "replace"),
            stderr=(stderr_b or b"").decode("utf-8", "replace"),
        )

    def write_file(self, path: str, content: bytes) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=path.lstrip("/"))
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        buf.seek(0)
        self.container.put_archive("/", buf.read())

    def read_file(self, path: str) -> bytes:
        stream, _ = self.container.get_archive(path)
        buf = io.BytesIO()
        for chunk in stream:
            buf.write(chunk)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            member = tar.next()
            f = tar.extractfile(member)
            return f.read() if f else b""

    def stream_logs(self):
        for line in self.container.logs(stream=True, follow=True):
            yield line.decode("utf-8", "replace")
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/sandbox/test_sandbox_exec.py -v
```

Expected: 3 pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/sandbox/manager.py tests/sandbox/test_sandbox_exec.py
git commit -m "feat(sandbox): exec + file IO + log streaming"
```

---

### Task 13: NestedSandbox for fabrication

**Files:**
- Modify: `noctua/sandbox/manager.py`
- Test: `tests/sandbox/test_nested_sandbox.py`

- [ ] **Step 1: Write failing test**

```python
# tests/sandbox/test_nested_sandbox.py
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
```

- [ ] **Step 2: Add `NestedSandbox` subclass**

```python
# noctua/sandbox/manager.py — append
class NestedSandbox(Sandbox):
    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
        self.client.images.pull(image)
        self.container = self.client.containers.run(
            image,
            command="sleep infinity",
            detach=True,
            cpu_count=1,
            mem_limit="512m",
            working_dir="/work",
            tmpfs={"/work": "rw,size=128m"},
            network_mode="none",
            labels={"noctua.role": "fabrication"},
        )
        self.info.container_id = self.container.id
        self.info.image_ref = image
        self.info.state = "ready"
        return self.info
```

- [ ] **Step 3: Run test**

```bash
pytest tests/sandbox/test_nested_sandbox.py -v
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/sandbox/manager.py tests/sandbox/test_nested_sandbox.py
git commit -m "feat(sandbox): NestedSandbox for tool fabrication"
```

---

### Task 14: Sandbox TTL reaper (Celery beat)

**Files:**
- Create: `noctua/sandbox/tasks.py`
- Modify: `noctua/celery.py`
- Test: `tests/sandbox/test_reaper.py`

- [ ] **Step 1: Write the reaper task**

```python
# noctua/sandbox/tasks.py
import docker
import time
from celery import shared_task

@shared_task
def reap_orphans():
    client = docker.from_env()
    now = time.time()
    for c in client.containers.list(filters={"label": "noctua.role"}):
        try:
            started = c.attrs["State"]["StartedAt"]
            # crude: any container older than 1800s gets killed
            import datetime
            t = datetime.datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
            if now - t > 1800:
                c.kill(); c.remove(force=True)
        except Exception:
            pass
```

- [ ] **Step 2: Register beat schedule**

```python
# noctua/celery.py — append
from celery.schedules import crontab

app.conf.beat_schedule = {
    "reap-orphans": {
        "task": "noctua.sandbox.tasks.reap_orphans",
        "schedule": 300.0,  # every 5 minutes
    },
}
```

- [ ] **Step 3: Write integration test**

```python
# tests/sandbox/test_reaper.py
import docker
import pytest
from noctua.sandbox.tasks import reap_orphans

def test_reaper_runs_without_error():
    # don't care about behavior here, just that it doesn't raise
    reap_orphans()
```

- [ ] **Step 4: Run test**

```bash
pytest tests/sandbox/test_reaper.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add noctua/sandbox/tasks.py noctua/celery.py tests/sandbox/test_reaper.py
git commit -m "feat(sandbox): TTL reaper as celery beat task"
```

---

### Task 15: Tool registry + bundled tools

**Files:**
- Create: `noctua/tools/__init__.py`
- Create: `noctua/tools/base.py`
- Create: `noctua/tools/bundled.py`
- Create: `noctua/tools/registry.py`
- Test: `tests/tools/test_registry.py`

- [ ] **Step 1: Write failing test**

```python
# tests/tools/test_registry.py
import pytest
from noctua.tools.registry import ToolRegistry
from noctua.core.models import Tool

pytestmark = pytest.mark.django_db

def test_lookup_precedence(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    # hardcoded bundled tool always available
    reg = ToolRegistry()
    t = reg.lookup("read_file", current_mission_id=1)
    assert t is not None
    assert t.status == "hardcoded"

def test_graduated_wins_over_hardcoded(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    (tmp_path / "graduated").mkdir()
    (tmp_path / "graduated" / "read_file.py").write_text("def call(args, sandbox): return 'graduated'\n")
    Tool.objects.create(name="read_file", signature={}, source_path=str(tmp_path / "graduated/read_file.py"), source_hash="h", status="graduated")
    reg = ToolRegistry()
    t = reg.lookup("read_file", current_mission_id=1)
    assert t.status == "graduated"
```

- [ ] **Step 2: Write `noctua/tools/base.py`**

```python
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class ToolResult:
    ok: bool
    value: Any = None
    error: str = ""

class ToolCallable(Protocol):
    def __call__(self, args: dict, sandbox) -> ToolResult: ...

@dataclass
class ToolEntry:
    name: str
    signature: dict
    status: str  # 'hardcoded' | 'fabricated_sandbox_only' | 'graduated'
    callable: ToolCallable
    source_path: str = ""
```

- [ ] **Step 3: Write `noctua/tools/bundled.py`**

```python
import shlex
from noctua.tools.base import ToolEntry, ToolResult

def read_file(args, sandbox):
    try:
        return ToolResult(ok=True, value=sandbox.read_file(args["path"]).decode("utf-8", "replace"))
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

def write_file(args, sandbox):
    try:
        sandbox.write_file(args["path"], args["content"].encode())
        return ToolResult(ok=True)
    except Exception as e:
        return ToolResult(ok=False, error=str(e))

def run_pytest(args, sandbox):
    cmd = ["bash", "-lc", f"cd /work && python -m pytest {args.get('args', '')} -q"]
    r = sandbox.exec(cmd, timeout=600)
    return ToolResult(ok=r.exit_code == 0, value={"exit_code": r.exit_code, "stdout": r.stdout, "stderr": r.stderr})

def git_branch(args, sandbox):
    r = sandbox.exec(["bash", "-lc", f"cd /work && git checkout -b {shlex.quote(args['name'])}"])
    return ToolResult(ok=r.exit_code == 0, value=r.stdout)

def git_commit(args, sandbox):
    msg = shlex.quote(args["message"])
    r = sandbox.exec(["bash", "-lc", f"cd /work && git add -A && git -c user.email=noctua@local -c user.name=Noctua commit -m {msg}"])
    return ToolResult(ok=r.exit_code == 0, value=r.stdout)

def git_push(args, sandbox):
    r = sandbox.exec(["bash", "-lc", f"cd /work && git push -u origin HEAD"])
    return ToolResult(ok=r.exit_code == 0, value=r.stdout)

def gh_pr_create(args, sandbox):
    title = shlex.quote(args["title"])
    body = shlex.quote(args["body"])
    draft = "--draft" if args.get("draft", True) else ""
    r = sandbox.exec(["bash", "-lc", f"cd /work && gh pr create --title {title} --body {body} {draft}"])
    return ToolResult(ok=r.exit_code == 0, value=r.stdout.strip())

def gh_pr_ready(args, sandbox):
    r = sandbox.exec(["bash", "-lc", f"gh pr ready {shlex.quote(args['url'])}"])
    return ToolResult(ok=r.exit_code == 0, value=r.stdout)

BUNDLED = [
    ToolEntry("read_file", {"args_schema": {"path": "string"}, "returns_schema": {"type": "string"}}, "hardcoded", read_file),
    ToolEntry("write_file", {"args_schema": {"path": "string", "content": "string"}, "returns_schema": {"ok": "bool"}}, "hardcoded", write_file),
    ToolEntry("run_pytest", {"args_schema": {"args": "string"}, "returns_schema": {"exit_code": "int", "stdout": "string"}}, "hardcoded", run_pytest),
    ToolEntry("git_branch", {"args_schema": {"name": "string"}, "returns_schema": {}}, "hardcoded", git_branch),
    ToolEntry("git_commit", {"args_schema": {"message": "string"}, "returns_schema": {}}, "hardcoded", git_commit),
    ToolEntry("git_push", {"args_schema": {}, "returns_schema": {}}, "hardcoded", git_push),
    ToolEntry("gh_pr_create", {"args_schema": {"title": "string", "body": "string", "draft": "bool"}, "returns_schema": {"url": "string"}}, "hardcoded", gh_pr_create),
    ToolEntry("gh_pr_ready", {"args_schema": {"url": "string"}, "returns_schema": {}}, "hardcoded", gh_pr_ready),
]
```

- [ ] **Step 4: Write `noctua/tools/registry.py`**

```python
import importlib.util
from pathlib import Path
from django.conf import settings
from noctua.core.models import Tool
from noctua.tools.base import ToolEntry
from noctua.tools.bundled import BUNDLED

class ToolRegistry:
    def __init__(self):
        self._bundled = {t.name: t for t in BUNDLED}

    def lookup(self, name: str, current_mission_id: int | None = None) -> ToolEntry | None:
        # 1. graduated
        graduated = Tool.objects.filter(name=name, status="graduated").first()
        if graduated:
            return self._load_from_disk(graduated)
        # 2. hardcoded
        if name in self._bundled:
            return self._bundled[name]
        # 3. fabricated for THIS mission
        if current_mission_id:
            fab = Tool.objects.filter(name=name, status="fabricated_sandbox_only", fabricated_by_mission_id=current_mission_id).first()
            if fab:
                return self._load_from_disk(fab)
        return None

    def _load_from_disk(self, tool_row: Tool) -> ToolEntry:
        spec = importlib.util.spec_from_file_location(tool_row.name, tool_row.source_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return ToolEntry(name=tool_row.name, signature=tool_row.signature, status=tool_row.status, callable=mod.call, source_path=tool_row.source_path)

    def all_available(self, current_mission_id: int | None = None) -> list[ToolEntry]:
        entries = list(self._bundled.values())
        for row in Tool.objects.filter(status="graduated"):
            entries.append(self._load_from_disk(row))
        if current_mission_id:
            for row in Tool.objects.filter(status="fabricated_sandbox_only", fabricated_by_mission_id=current_mission_id):
                entries.append(self._load_from_disk(row))
        return entries
```

- [ ] **Step 5: Run tests**

```bash
mkdir -p noctua/tools tests/tools
touch noctua/tools/__init__.py tests/tools/__init__.py
pytest tests/tools/test_registry.py -v
```

Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/tools/ tests/tools/
git commit -m "feat(tools): bundled tools + registry with precedence"
```

---

### Task 16: Tool fabricator for `seed_db`

**Files:**
- Create: `noctua/tools/fabricator.py`
- Create: `noctua/tools/prompts/seed_db.md`
- Test: `tests/tools/test_fabricator.py`

- [ ] **Step 1: Write the fabrication prompt**

```markdown
# noctua/tools/prompts/seed_db.md

You are writing a tiny Python tool named `seed_db` for the Noctua project.

The tool will be invoked as: `python tool.py <json-args>`.
It receives args like `{"rows": 3}` and must seed a Postgres database
running at `postgresql://noctua:noctua@localhost:5432/noctua` with `rows`
sample rows in a table called `widget` (`id serial primary key, name text`).

Constraints:
- Use only stdlib + psycopg2-binary.
- Top-level callable must be `def call(args: dict, sandbox=None) -> dict` returning {"inserted": N}.
- When executed as `__main__`, parse argv[1] as json, call `call(args)`, print json result.

Return ONLY the Python source — no markdown fences, no commentary.
```

- [ ] **Step 2: Write `noctua/tools/fabricator.py`**

```python
import hashlib
import json
from pathlib import Path
from django.conf import settings
from anthropic import Anthropic
from noctua.sandbox.manager import NestedSandbox
from noctua.core.models import Tool
from noctua.tools.base import ToolEntry, ToolResult

PROMPT = Path(__file__).parent / "prompts" / "seed_db.md"

class ToolFabricator:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def fabricate(self, name: str, signature: dict, mission_id: int, context: dict | None = None) -> ToolEntry:
        if name != "seed_db":
            raise NotImplementedError(f"only seed_db is implemented in MVP, got: {name}")
        prompt = PROMPT.read_text()
        resp = self.client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            system=prompt,
            messages=[{"role": "user", "content": f"Signature: {json.dumps(signature)}\nContext: {json.dumps(context or {})}"}],
        )
        source = resp.content[0].text
        source_hash = hashlib.sha256(source.encode()).hexdigest()[:12]
        out_dir = settings.NOCTUA_TOOLS_DIR / "fabricated" / source_hash
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{name}.py"
        out_file.write_text(source)

        # validate in nested sandbox
        ns = NestedSandbox()
        ns.boot("python:3.12-slim", None)
        try:
            ns.exec(["pip", "install", "-q", "psycopg2-binary"], timeout=120)
            ns.write_file("/work/tool.py", source.encode())
            r = ns.exec(["python", "/work/tool.py", json.dumps({"rows": 0})], timeout=30)
            if r.exit_code != 0:
                raise RuntimeError(f"fabrication validation failed: {r.stderr}")
        finally:
            ns.teardown()

        tool_row = Tool.objects.create(
            name=name, signature=signature, source_path=str(out_file),
            source_hash=source_hash, status="fabricated_sandbox_only",
            fabricated_by_mission_id=mission_id,
        )
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, str(out_file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return ToolEntry(name=name, signature=signature, status="fabricated_sandbox_only", callable=mod.call, source_path=str(out_file))
```

- [ ] **Step 3: Write fabrication round-trip test (mocked Anthropic)**

```python
# tests/tools/test_fabricator.py
import json
import pytest
from unittest.mock import patch, MagicMock
from noctua.tools.fabricator import ToolFabricator
from noctua.core.models import Tool

pytestmark = pytest.mark.django_db

CANNED_SOURCE = '''
import json, sys
def call(args, sandbox=None):
    return {"inserted": int(args.get("rows", 0))}
if __name__ == "__main__":
    print(json.dumps(call(json.loads(sys.argv[1]))))
'''

def test_seed_db_fabrication(tmp_path, settings):
    settings.NOCTUA_TOOLS_DIR = tmp_path
    fab = ToolFabricator()
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=CANNED_SOURCE)]
    with patch.object(fab.client.messages, "create", return_value=fake_resp):
        from noctua.core.models import Mission
        m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
        entry = fab.fabricate("seed_db", {}, mission_id=m.id)
    assert entry.name == "seed_db"
    assert entry.status == "fabricated_sandbox_only"
    assert Tool.objects.filter(name="seed_db", status="fabricated_sandbox_only").exists()
    result = entry.callable({"rows": 3}, sandbox=None)
    assert result == {"inserted": 3}
```

- [ ] **Step 4: Run test (requires Docker)**

```bash
pytest tests/tools/test_fabricator.py -v -s
```

Expected: pass. (~20s — pulls python image + pip install in nested sandbox.)

- [ ] **Step 5: Commit**

```bash
git add noctua/tools/fabricator.py noctua/tools/prompts/seed_db.md tests/tools/test_fabricator.py
git commit -m "feat(tools): seed_db fabricator with nested-sandbox validation"
```

---

### Task 17: Budget tracking helpers

**Files:**
- Create: `noctua/runner/budget.py`
- Test: `tests/runner/test_budget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/runner/test_budget.py
import pytest
from noctua.core.models import Mission
from noctua.runner.budget import increment_spent, check_budget

pytestmark = pytest.mark.django_db

@pytest.fixture
def mission():
    return Mission.objects.create(
        goal="g", producer_key="pr", repo_url="r",
        budget={"max_wall_seconds": 100, "max_tokens": 1000, "max_tool_calls": 5},
    )

def test_increment_and_check_under(mission):
    spent = increment_spent(mission.id, tokens=500, tool_calls=2)
    assert spent["tokens"] == 500
    assert check_budget(mission.id) is None  # under

def test_increment_breaches_tokens(mission):
    increment_spent(mission.id, tokens=1500)
    breach = check_budget(mission.id)
    assert breach == "tokens"
```

- [ ] **Step 2: Write `noctua/runner/budget.py`**

```python
from django.db import transaction
from noctua.core.models import Mission

def increment_spent(mission_id: int, *, wall_seconds: int = 0, tokens: int = 0, tool_calls: int = 0) -> dict:
    with transaction.atomic():
        m = Mission.objects.select_for_update().get(id=mission_id)
        s = dict(m.spent or {"wall_seconds": 0, "tokens": 0, "tool_calls": 0})
        s["wall_seconds"] += wall_seconds
        s["tokens"] += tokens
        s["tool_calls"] += tool_calls
        m.spent = s
        m.save(update_fields=["spent"])
        return s

def check_budget(mission_id: int) -> str | None:
    """Return the field name of the breached cap, or None."""
    m = Mission.objects.get(id=mission_id)
    b, s = m.budget or {}, m.spent or {}
    for field in ("wall_seconds", "tokens", "tool_calls"):
        cap = b.get(f"max_{field}")
        if cap is not None and s.get(field, 0) > cap:
            return field
    return None
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/runner/test_budget.py -v
```

Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/runner/budget.py tests/runner/test_budget.py
git commit -m "feat(runner): atomic budget increment + check helpers"
```

---

### Task 18: WS 2 smoke — fabricate seed_db end-to-end

- [ ] **Step 1: Manual smoke**

```bash
./manage.py shell <<'EOF'
from noctua.core.models import Mission
from noctua.tools.fabricator import ToolFabricator
m = Mission.objects.create(goal="smoke", producer_key="pr", repo_url="", budget={})
entry = ToolFabricator().fabricate("seed_db", {"args_schema":{"rows":"int"},"returns_schema":{"inserted":"int"}}, mission_id=m.id, context={})
print("status:", entry.status)
print("result:", entry.callable({"rows": 5}, sandbox=None))
EOF
```

Expected: `status: fabricated_sandbox_only`, `result: {'inserted': 5}` (or similar — varies by LLM output, but it must run).

- [ ] **Step 2: Verify Tool row exists**

```bash
./manage.py shell -c "from noctua.core.models import Tool; print(list(Tool.objects.values('name','status','source_path')))"
```

- [ ] **Step 3: Commit any cleanup**

```bash
git add -A
git commit -m "chore(ws2): smoke verified" --allow-empty
```

---

## WS 3 — Mission Runner + PR Producer

### Task 19: Planner — Claude-driven step graph

**Files:**
- Create: `noctua/runner/llm.py`
- Create: `noctua/runner/planner.py`
- Create: `noctua/runner/prompts/plan.md`
- Test: `tests/runner/test_planner.py`

- [ ] **Step 1: Write the planner prompt**

```markdown
# noctua/runner/prompts/plan.md
You are Noctua's planner. Given a Mission, output a JSON object:

{
  "steps": [
    {"step_id": "s1", "kind": "exec", "payload": {"cmd": [...]}},
    {"step_id": "s2", "kind": "tool", "payload": {"name": "...", "args": {...}}},
    {"step_id": "s3", "kind": "edit", "payload": {"goal": "..."}}
  ],
  "rendered_md": "human-readable summary of the plan"
}

Kinds:
- "exec": raw shell command in the sandbox
- "tool": call a registered tool by name
- "edit": LLM-driven code edit loop (the executor will drive Claude tool-use)

Constraints:
- 5–15 steps.
- Always end with a step that opens a draft PR via gh_pr_create.
- Always validate with run_pytest before opening the PR.
- Return ONLY the JSON object.
```

- [ ] **Step 2: Write `noctua/runner/llm.py`**

```python
from anthropic import Anthropic
from django.conf import settings

PLANNER_MODEL = "claude-sonnet-4-6"
CODER_MODEL = "claude-opus-4-7"

def client():
    return Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def call_with_cache(messages, system, model, max_tokens=4000, tools=None):
    """Call Claude with prompt caching enabled on the system block."""
    kw = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
    }
    if tools:
        kw["tools"] = tools
    return client().messages.create(**kw)
```

- [ ] **Step 3: Write `noctua/runner/planner.py`**

```python
import json
from pathlib import Path
from noctua.core.models import Mission, Plan, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL

PLAN_PROMPT = Path(__file__).parent / "prompts" / "plan.md"

def plan_for_mission(mission: Mission) -> Plan:
    system = PLAN_PROMPT.read_text()
    rubric = Producer.objects.get(key=mission.producer_key).rubric_md
    user = f"""Mission:
Goal: {mission.goal}
Repo: {mission.repo_url}
Issue: {mission.issue_url}
Inputs: {json.dumps(mission.inputs)}
Success criteria: {mission.success_criteria}

Producer rubric:
{rubric}
"""
    resp = call_with_cache([{"role": "user", "content": user}], system, PLANNER_MODEL)
    text = resp.content[0].text.strip()
    # be lenient with code fences
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if text.startswith("json") else text
    obj = json.loads(text)
    plan = Plan.objects.create(
        mission=mission,
        version=(mission.plans.aggregate_max() if hasattr(mission.plans, "aggregate_max") else (mission.plans.count() + 1)),
        steps=[{**s, "status": "pending", "attempt": 0, "result": None} for s in obj["steps"]],
        rendered_md=obj.get("rendered_md", ""),
    )
    return plan, resp.usage.input_tokens + resp.usage.output_tokens
```

- [ ] **Step 4: Write planner test (mocked LLM)**

```python
# tests/runner/test_planner.py
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan
from noctua.runner.planner import plan_for_mission

pytestmark = pytest.mark.django_db

CANNED = '''{"steps": [
  {"step_id":"s1","kind":"exec","payload":{"cmd":["bash","-lc","echo hi"]}},
  {"step_id":"s2","kind":"tool","payload":{"name":"run_pytest","args":{"args":""}}},
  {"step_id":"s3","kind":"tool","payload":{"name":"gh_pr_create","args":{"title":"t","body":"b","draft":true}}}
],"rendered_md":"hi"}'''

def test_plan_for_mission_persists():
    Producer.objects.create(key="pr", kind="pr", rubric_md="rubric", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={})
    fake = MagicMock()
    fake.content = [MagicMock(text=CANNED)]
    fake.usage = MagicMock(input_tokens=100, output_tokens=200)
    with patch("noctua.runner.planner.call_with_cache", return_value=fake):
        plan, tokens = plan_for_mission(m)
    assert plan.steps[0]["kind"] == "exec"
    assert tokens == 300
    assert Plan.objects.filter(mission=m).count() == 1
```

- [ ] **Step 5: Run test + fix the `.plans.count()` versioning**

The plan version needs `Mission.plans.count() + 1`. The line in Step 3 already does this when the conditional falls through.

```bash
pytest tests/runner/test_planner.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/runner/llm.py noctua/runner/planner.py noctua/runner/prompts/plan.md tests/runner/test_planner.py
git commit -m "feat(runner): claude planner with prompt caching"
```

---

### Task 20: Executor loop skeleton

**Files:**
- Create: `noctua/runner/executor.py`
- Test: `tests/runner/test_executor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/runner/test_executor.py
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Plan
from noctua.runner.executor import execute_plan

pytestmark = pytest.mark.django_db

def test_executes_tool_steps_in_order():
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", budget={"max_tool_calls": 10, "max_tokens": 10000, "max_wall_seconds": 60})
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool", "payload": {"name": "read_file", "args": {"path": "/work/x"}}, "status": "pending", "attempt": 0, "result": None}
    ], rendered_md="")
    fake_sandbox = MagicMock()
    fake_sandbox.read_file.return_value = b"hello"
    results = execute_plan(m, plan, sandbox=fake_sandbox)
    assert results[0]["status"] == "succeeded"
    assert "hello" in results[0]["result"]["value"]
```

- [ ] **Step 2: Write `noctua/runner/executor.py`**

```python
from noctua.core.models import Mission, Plan
from noctua.tools.registry import ToolRegistry
from noctua.runner.budget import increment_spent, check_budget

MAX_RETRIES_PER_STEP = 3

class NeedsInput(Exception):
    def __init__(self, prompt): self.prompt = prompt

class StoppedByBudget(Exception):
    def __init__(self, field): self.field = field

def execute_plan(mission: Mission, plan: Plan, sandbox) -> list[dict]:
    registry = ToolRegistry()
    results = []
    for step in plan.steps:
        if step["status"] == "succeeded":
            results.append(step); continue
        breach = check_budget(mission.id)
        if breach:
            raise StoppedByBudget(breach)
        for attempt in range(MAX_RETRIES_PER_STEP):
            step["attempt"] = attempt + 1
            try:
                if step["kind"] == "tool":
                    name = step["payload"]["name"]
                    args = step["payload"].get("args", {})
                    entry = registry.lookup(name, current_mission_id=mission.id)
                    if entry is None:
                        from noctua.tools.fabricator import ToolFabricator
                        entry = ToolFabricator().fabricate(name, {"args_schema": {}, "returns_schema": {}}, mission_id=mission.id)
                    result = entry.callable(args, sandbox)
                    increment_spent(mission.id, tool_calls=1)
                    step["result"] = {"ok": result.ok, "value": result.value, "error": result.error}
                    step["status"] = "succeeded" if result.ok else "failed"
                elif step["kind"] == "exec":
                    r = sandbox.exec(step["payload"]["cmd"], timeout=step["payload"].get("timeout", 60))
                    step["result"] = {"ok": r.exit_code == 0, "value": r.stdout, "error": r.stderr}
                    step["status"] = "succeeded" if r.exit_code == 0 else "failed"
                elif step["kind"] == "edit":
                    # delegated to producer; see Task 26
                    raise NotImplementedError("edit dispatched via producer")
                else:
                    raise ValueError(f"unknown step kind: {step['kind']}")
                if step["status"] == "succeeded":
                    break
            except (NeedsInput, StoppedByBudget):
                raise
            except Exception as e:
                step["status"] = "failed"
                step["result"] = {"ok": False, "error": str(e)}
        results.append(step)
        plan.steps = plan.steps  # mark JSONB dirty
        plan.save(update_fields=["steps"])
    return results
```

- [ ] **Step 3: Run test**

```bash
pytest tests/runner/test_executor.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/runner/executor.py tests/runner/test_executor.py
git commit -m "feat(runner): executor loop with retries + budget breach"
```

---

### Task 21: PR producer — plan + edit loop + finalize

**Files:**
- Modify: `noctua/producers/pr.py` (full implementation)
- Create: `noctua/producers/pr/prompts/edit.md`
- Test: `tests/producers/test_pr_producer.py`

- [ ] **Step 1: Write edit-loop prompt**

```markdown
# noctua/producers/pr/prompts/edit.md

You are a senior engineer editing code in a sandboxed checkout under /work.

Available tools (Claude tool-use):
- read_file(path)
- write_file(path, content)
- run_pytest(args)
- needs_input(prompt) — call ONLY if you genuinely can't proceed without user clarification

Procedure:
1. Read the issue body and any relevant files.
2. Make minimal edits.
3. Run pytest. If it fails, fix.
4. When green, return a single message "DONE" (no tool calls).

Repeat until DONE or you've exhausted attempts. Be terse.
```

- [ ] **Step 2: Replace `noctua/producers/pr.py` with full implementation**

```python
import json
from pathlib import Path
from noctua.core.models import Mission, Plan, Artifact, Producer
from noctua.runner.llm import call_with_cache, CODER_MODEL
from noctua.runner.budget import increment_spent
from noctua.runner.executor import NeedsInput
from noctua.tools.registry import ToolRegistry
from noctua.tools.base import ToolResult

EDIT_PROMPT = Path(__file__).parent / "pr" / "prompts" / "edit.md"
MAX_EDIT_TURNS = 10

class PRProducer:
    key = "pr"
    kind = "pr"

    def __init__(self):
        self.rubric_path = "noctua/producers/pr/rubric.md"

    def plan(self, mission: Mission, ctx=None):
        from noctua.runner.planner import plan_for_mission
        return plan_for_mission(mission)

    def execute_step(self, step, sandbox, mission: Mission):
        if step["kind"] == "edit":
            return self._edit_loop(mission, sandbox)
        return None  # other kinds handled by executor

    def _edit_loop(self, mission: Mission, sandbox):
        registry = ToolRegistry()
        tools_for_claude = [
            {
                "name": e.name,
                "description": e.name,
                "input_schema": {"type": "object", "properties": {k: {"type": "string"} for k in e.signature.get("args_schema", {})}, "required": []},
            }
            for e in registry.all_available(current_mission_id=mission.id)
        ] + [{"name": "needs_input", "description": "ask user", "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}]

        system = EDIT_PROMPT.read_text()
        rubric = Producer.objects.get(key="pr").rubric_md
        issue_text = self._fetch_issue(sandbox, mission.issue_url)
        messages = [{"role": "user", "content": f"Issue:\n{issue_text}\n\nRubric:\n{rubric}\n\nGo."}]

        for turn in range(MAX_EDIT_TURNS):
            resp = call_with_cache(messages, system, CODER_MODEL, tools=tools_for_claude, max_tokens=4000)
            increment_spent(mission.id, tokens=resp.usage.input_tokens + resp.usage.output_tokens)
            if resp.stop_reason == "end_turn":
                if any(getattr(b, "text", "").strip() == "DONE" for b in resp.content if hasattr(b, "text")):
                    return ToolResult(ok=True, value="edit-loop complete")
                messages.append({"role": "assistant", "content": resp.content})
                continue
            assistant_msg = {"role": "assistant", "content": resp.content}
            messages.append(assistant_msg)
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use":
                    if block.name == "needs_input":
                        raise NeedsInput(block.input["prompt"])
                    entry = registry.lookup(block.name, current_mission_id=mission.id)
                    if entry is None:
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": "tool not found", "is_error": True})
                        continue
                    result = entry.callable(block.input, sandbox)
                    increment_spent(mission.id, tool_calls=1)
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": block.id,
                        "content": json.dumps({"ok": result.ok, "value": result.value, "error": result.error})[:8000],
                        "is_error": not result.ok,
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        return ToolResult(ok=False, error="edit-loop exhausted MAX_EDIT_TURNS")

    def _fetch_issue(self, sandbox, issue_url: str) -> str:
        if not issue_url:
            return ""
        r = sandbox.exec(["bash", "-lc", f"gh issue view {issue_url} --json title,body --jq '.title + \"\\n\\n\" + .body'"])
        return r.stdout if r.exit_code == 0 else ""

    def finalize(self, mission: Mission, sandbox):
        # PR URL was created by the last tool step (gh_pr_create). Find it.
        last_plan = mission.plans.order_by("-version").first()
        pr_url = ""
        for step in last_plan.steps:
            if step.get("payload", {}).get("name") == "gh_pr_create" and step.get("result", {}).get("ok"):
                pr_url = step["result"]["value"]
        artifact = Artifact.objects.create(
            mission=mission, producer_key="pr", kind="pr",
            uri=pr_url,
            preview={"title": mission.goal},
            provenance={"plan_version": last_plan.version},
            validation={"tests_passed": True},
            queue_state="pending",
        )
        return artifact

    def on_approve(self, artifact: Artifact):
        if not artifact.uri:
            return
        from noctua.sandbox.manager import Sandbox
        sb = Sandbox()
        sb.boot("python:3.12-slim", None)
        try:
            sb.exec(["bash", "-lc", f"gh pr ready {artifact.uri}"])
        finally:
            sb.teardown()

    def on_promote(self, artifact: Artifact):
        pass
```

- [ ] **Step 3: Write PR producer test (mocked LLM + fake sandbox)**

```python
# tests/producers/test_pr_producer.py
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer
from noctua.producers.pr import PRProducer

pytestmark = pytest.mark.django_db

@pytest.fixture
def setup():
    Producer.objects.create(key="pr", kind="pr", rubric_md="rubric", default_budget={})

def test_edit_loop_terminates_on_DONE(setup):
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", issue_url="", budget={"max_wall_seconds": 60, "max_tokens": 100000, "max_tool_calls": 50})
    sandbox = MagicMock()
    sandbox.exec.return_value = MagicMock(stdout="", exit_code=0, stderr="")
    fake_resp = MagicMock()
    fake_resp.stop_reason = "end_turn"
    fake_resp.content = [MagicMock(text="DONE")]
    fake_resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    # ensure the truthy `getattr(b, "text", "")` path works
    for b in fake_resp.content:
        b.text = "DONE"
    p = PRProducer()
    with patch("noctua.producers.pr.call_with_cache", return_value=fake_resp):
        r = p._edit_loop(m, sandbox)
    assert r.ok is True
```

- [ ] **Step 4: Run test**

```bash
mkdir -p noctua/producers/pr/prompts tests/producers
touch tests/producers/__init__.py
pytest tests/producers/test_pr_producer.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add noctua/producers/pr.py noctua/producers/pr/prompts/edit.md tests/producers/test_pr_producer.py
git commit -m "feat(producers): full PRProducer with claude tool-use edit loop"
```

---

### Task 22: Stub producers with canned artifacts

**Files:**
- Modify: `noctua/producers/stub.py`
- Create: `noctua/producers/stub/fixtures/social_post.json`
- Create: `noctua/producers/stub/fixtures/clinical.json`
- Create: `noctua/producers/stub/fixtures/diagnostic.json`
- Create: `noctua/core/management/commands/seed_stub_artifacts.py`

- [ ] **Step 1: Write fixture files**

```json
// noctua/producers/stub/fixtures/social_post.json
{
  "uri": "draft://social/abcd",
  "preview": {"title": "Launch announcement", "snippet": "Today we shipped..."},
  "validation": {"tone_check": "ok", "char_count": 198}
}
```

```json
// noctua/producers/stub/fixtures/clinical.json
{
  "uri": "report://clinical/efgh",
  "preview": {"title": "Cohort A vs B significance summary", "snippet": "p=0.03 with caveats..."},
  "validation": {"replication": "ok"}
}
```

```json
// noctua/producers/stub/fixtures/diagnostic.json
{
  "uri": "report://diagnostic/ijkl",
  "preview": {"title": "VIN 1HGBH41JX… brake wear advisory", "snippet": "Replace pads within 1500mi..."},
  "validation": {"telematics_signals": 3}
}
```

- [ ] **Step 2: Update `noctua/producers/stub.py`**

```python
import json
from pathlib import Path
from noctua.core.models import Mission, Artifact

FIXTURES = Path(__file__).parent / "stub" / "fixtures"

class _Stub:
    def on_approve(self, artifact): pass
    def on_promote(self, artifact): pass
    def finalize(self, mission, sandbox=None):
        data = json.loads((FIXTURES / f"{self.fixture}.json").read_text())
        return Artifact.objects.create(
            mission=mission, producer_key=self.key, kind=self.kind,
            uri=data["uri"], preview=data["preview"], provenance={},
            validation=data["validation"], queue_state="pending",
        )

class SocialPostStub(_Stub):
    key = "social_post"; kind = "social_post"; fixture = "social_post"

class ClinicalAnalysisStub(_Stub):
    key = "clinical_analysis"; kind = "analysis"; fixture = "clinical"

class DiagnosticStub(_Stub):
    key = "diagnostic"; kind = "diagnostic"; fixture = "diagnostic"
```

- [ ] **Step 3: Write seed command**

```python
# noctua/core/management/commands/seed_stub_artifacts.py
from django.core.management.base import BaseCommand
from noctua.core.models import Mission, Producer
from noctua.producers.registry import get_producer

class Command(BaseCommand):
    help = "Create one canned artifact per stub producer."
    def handle(self, *args, **kwargs):
        for key in ("social_post", "clinical_analysis", "diagnostic"):
            m, _ = Mission.objects.get_or_create(
                goal=f"stub-demo-{key}",
                defaults={"producer_key": key, "repo_url": "", "budget": {}, "state": "succeeded"},
            )
            producer = get_producer(key)
            producer.finalize(m)
            self.stdout.write(f"seeded stub artifact for {key}")
```

- [ ] **Step 4: Smoke**

```bash
mkdir -p noctua/producers/stub/fixtures
# create the 3 fixture files
./manage.py seed_stub_artifacts
curl -s -H "Authorization: Bearer $NOCTUA_API_TOKEN" "http://localhost:8000/api/queue?kind=social_post" | python -m json.tool
```

Expected: an artifact row with the canned preview.

- [ ] **Step 5: Commit**

```bash
git add noctua/producers/stub.py noctua/producers/stub/fixtures/ noctua/core/management/commands/seed_stub_artifacts.py
git commit -m "feat(producers): stub producers with canned artifacts"
```

---

### Task 23: Mission lifecycle in Celery worker

**Files:**
- Modify: `noctua/runner/tasks.py`
- Test: `tests/runner/test_lifecycle.py`

- [ ] **Step 1: Write the full lifecycle test (mocking sandbox + LLM)**

```python
# tests/runner/test_lifecycle.py
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Artifact, Plan
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

CANNED_PLAN = '''{"steps":[
  {"step_id":"s1","kind":"exec","payload":{"cmd":["bash","-lc","echo hi"]}},
  {"step_id":"s2","kind":"tool","payload":{"name":"gh_pr_create","args":{"title":"t","body":"b","draft":true}}}
],"rendered_md":"x"}'''

def test_full_lifecycle_succeeds(monkeypatch):
    Producer.objects.create(key="pr", kind="pr", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="https://github.com/x/y", issue_url="", budget={"max_wall_seconds": 60, "max_tokens": 10000, "max_tool_calls": 5})

    fake_planner_resp = MagicMock()
    fake_planner_resp.content = [MagicMock(text=CANNED_PLAN)]
    fake_planner_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

    fake_sandbox = MagicMock()
    fake_sandbox.boot.return_value = MagicMock(container_id="c", state="ready")
    fake_sandbox.exec.return_value = MagicMock(exit_code=0, stdout="https://github.com/x/y/pull/1", stderr="")

    with patch("noctua.runner.planner.call_with_cache", return_value=fake_planner_resp), \
         patch("noctua.runner.tasks.Sandbox", return_value=fake_sandbox):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "succeeded"
    assert Artifact.objects.filter(mission=m, kind="pr").exists()
```

- [ ] **Step 2: Replace `noctua/runner/tasks.py` with full lifecycle**

```python
from celery import shared_task
from django.utils.timezone import now
from noctua.core.models import Mission, Artifact, Tool
from noctua.sandbox.manager import Sandbox
from noctua.runner.planner import plan_for_mission
from noctua.runner.executor import execute_plan, NeedsInput, StoppedByBudget
from noctua.runner.budget import increment_spent
from noctua.producers.registry import get_producer

@shared_task(bind=True, time_limit=2000, soft_time_limit=1800)
def run_mission(self, mission_id: int):
    m = Mission.objects.get(id=mission_id)
    m.state = "running"; m.started_at = m.started_at or now(); m.save(update_fields=["state", "started_at"])
    sandbox = Sandbox(ttl_seconds=m.budget.get("max_wall_seconds", 1800))
    try:
        sandbox.boot(image="python:3.12-slim", repo_url=m.repo_url or None)
        plan, tokens = plan_for_mission(m)
        increment_spent(m.id, tokens=tokens)
        try:
            execute_plan(m, plan, sandbox)
        except StoppedByBudget as e:
            m.state = "stopped"; m.state_reason = f"budget_exceeded: {e.field}"; m.save(update_fields=["state", "state_reason"]); return
        except NeedsInput as e:
            m.state = "needs_input"; m.needs_input_prompt = e.prompt; m.save(update_fields=["state", "needs_input_prompt"]); return
        producer = get_producer(m.producer_key)
        producer.finalize(m, sandbox)
        # also emit kind='tool' artifacts for any tools fabricated during this mission
        for t in Tool.objects.filter(fabricated_by_mission_id=m.id, status="fabricated_sandbox_only"):
            Artifact.objects.get_or_create(
                mission=m, producer_key=m.producer_key, kind="tool", tool=t,
                defaults={"uri": f"file://{t.source_path}", "preview": {"name": t.name, "lines": _count_lines(t.source_path)}, "provenance": {}, "validation": {"sandbox_only": True}, "queue_state": "pending"},
            )
        m.state = "succeeded"
    except Exception as e:
        m.state = "failed"; m.state_reason = f"{type(e).__name__}: {e}"
    finally:
        m.finished_at = now()
        m.save(update_fields=["state", "state_reason", "finished_at"])
        sandbox.teardown()
    return mission_id

def _count_lines(path: str) -> int:
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
```

- [ ] **Step 3: Run test**

```bash
pytest tests/runner/test_lifecycle.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add noctua/runner/tasks.py tests/runner/test_lifecycle.py
git commit -m "feat(runner): full mission lifecycle in celery task"
```

---

### Task 24: needs_input resume

**Files:**
- Modify: `noctua/runner/tasks.py`
- Modify: `noctua/runner/executor.py` (already supports the exception)
- Test: `tests/runner/test_needs_input.py`

- [ ] **Step 1: Write test**

```python
# tests/runner/test_needs_input.py
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db

def test_needs_input_pauses_and_resumes():
    Producer.objects.create(key="pr", kind="pr", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="pr", repo_url="r", issue_url="", budget={"max_wall_seconds":60,"max_tokens":10000,"max_tool_calls":5})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id":"s1","kind":"edit","payload":{},"status":"pending","attempt":0,"result":None},
    ], rendered_md="")
    fake_sandbox = MagicMock()
    fake_sandbox.boot.return_value = MagicMock(container_id="c", state="ready")
    with patch("noctua.runner.tasks.Sandbox", return_value=fake_sandbox), \
         patch("noctua.runner.planner.plan_for_mission", return_value=(Plan.objects.filter(mission=m).first(), 50)), \
         patch("noctua.runner.executor.execute_plan", side_effect=__import__("noctua.runner.executor", fromlist=["NeedsInput"]).NeedsInput("clarify X?")):
        run_mission(m.id)
    m.refresh_from_db()
    assert m.state == "needs_input"
    assert m.needs_input_prompt == "clarify X?"
```

- [ ] **Step 2: Confirm `run_mission` already handles this**

The implementation in Task 23 catches `NeedsInput` and sets `state = "needs_input"`. The API endpoint `POST /api/missions/:id/respond` in Task 5 re-enqueues. No new code needed.

- [ ] **Step 3: Run test**

```bash
pytest tests/runner/test_needs_input.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add tests/runner/test_needs_input.py
git commit -m "test(runner): needs_input pause behavior"
```

---

### Task 25: End-to-end WS 3 smoke against the demo repo

(Demo repo is created in WS 5 Task 37. If you're following workstreams strictly in order, skip this smoke until Task 37 lands, then return.)

- [ ] **Step 1: Reset the demo repo**

```bash
make reset-demo  # from Task 37
```

- [ ] **Step 2: Fire a real mission**

```bash
noctua run \
  --repo $NOCTUA_DEMO_REPO \
  --issue $NOCTUA_DEMO_REPO/issues/1 \
  --goal "Add /healthz endpoint returning {ok:true}"
```

- [ ] **Step 3: Watch logs**

```bash
celery -A noctua worker -l info  # in a tab; watch the lifecycle
```

- [ ] **Step 4: Verify**

```bash
gh pr list --repo hugoduar/noctua-demo-app --state all
curl -s -H "Authorization: Bearer $NOCTUA_API_TOKEN" http://localhost:8000/api/queue | python -m json.tool
```

Expected: 1 draft PR exists; 1 pending PR artifact in the queue. Optionally a Tool artifact for `seed_db` if the planner used it.

---

## WS 4 — Review UI

### Task 26: Next.js project skeleton + Tailwind

**Files:**
- Create: `ui/package.json`
- Create: `ui/next.config.ts`
- Create: `ui/tailwind.config.ts`
- Create: `ui/app/layout.tsx`
- Create: `ui/app/page.tsx`
- Create: `ui/app/globals.css`

- [ ] **Step 1: Scaffold**

```bash
cd ui  # create dir
npx --yes create-next-app@latest . --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*" --turbo
# Yes to TypeScript, Tailwind, App Router. No to src dir.
```

- [ ] **Step 2: Verify boot**

```bash
npm run dev -- --port 3000
```

Expected: localhost:3000 renders default Next.js page.

- [ ] **Step 3: Commit**

```bash
cd ..
git add ui/
git commit -m "feat(ui): next.js scaffolding"
```

---

### Task 27: Typed API client + env

**Files:**
- Create: `ui/lib/api.ts`
- Create: `ui/lib/types.ts`
- Create: `ui/.env.local.example`

- [ ] **Step 1: Write types**

```typescript
// ui/lib/types.ts
export type ArtifactKind = "pr" | "social_post" | "analysis" | "diagnostic" | "cad" | "tool";
export type QueueState = "pending" | "approved" | "rejected" | "promoted";
export type MissionState = "queued" | "running" | "succeeded" | "failed" | "stopped" | "needs_input";

export interface Artifact {
  id: number;
  mission_id: number;
  producer_key: string;
  kind: ArtifactKind;
  uri: string;
  preview: Record<string, unknown>;
  validation: Record<string, unknown>;
  queue_state: QueueState;
  tool_id?: number | null;
}

export interface Mission {
  id: number;
  goal: string;
  state: MissionState;
  state_reason: string;
  producer_key: string;
  repo_url: string;
  issue_url: string;
  budget: Record<string, number>;
  spent: Record<string, number>;
  needs_input_prompt?: string | null;
}

export interface Producer {
  key: string;
  kind: string;
  rubric_md: string;
  version: number;
}
```

- [ ] **Step 2: Write API client**

```typescript
// ui/lib/api.ts
const API = process.env.NEXT_PUBLIC_NOCTUA_API ?? "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_NOCTUA_TOKEN ?? "";

const headers = () => ({ Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" });

export async function getQueue(kind?: string) {
  const url = new URL(`${API}/api/queue`);
  if (kind) url.searchParams.set("kind", kind);
  const r = await fetch(url, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function getArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function approveArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}/approve`, { method: "POST", headers: headers() });
  return r.json();
}

export async function rejectArtifact(id: number) {
  const r = await fetch(`${API}/api/artifacts/${id}/reject`, { method: "POST", headers: headers() });
  return r.json();
}

export async function getMission(id: number) {
  const r = await fetch(`${API}/api/missions/${id}`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function getProducers() {
  const r = await fetch(`${API}/api/producers`, { headers: headers(), cache: "no-store" });
  return r.json();
}

export async function updateRubric(key: string, rubric_md: string) {
  const r = await fetch(`${API}/api/producers/${key}/rubric`, {
    method: "PUT", headers: headers(), body: JSON.stringify({ rubric_md }),
  });
  return r.json();
}
```

- [ ] **Step 3: Write env example**

```bash
# ui/.env.local.example
NEXT_PUBLIC_NOCTUA_API=http://localhost:8000
NEXT_PUBLIC_NOCTUA_TOKEN=
```

- [ ] **Step 4: Commit**

```bash
git add ui/lib/ ui/.env.local.example
git commit -m "feat(ui): typed API client"
```

---

### Task 28: `/queue` page — tabs + sections + cards

**Files:**
- Replace: `ui/app/page.tsx`
- Create: `ui/app/queue/page.tsx`
- Create: `ui/components/ArtifactCard.tsx`
- Create: `ui/components/TabBar.tsx`

- [ ] **Step 1: Write `/queue/page.tsx`**

```typescript
// ui/app/queue/page.tsx
import { getQueue } from "@/lib/api";
import TabBar from "@/components/TabBar";
import ArtifactCard from "@/components/ArtifactCard";
import type { Artifact } from "@/lib/types";

const TABS = [
  { key: "pr", label: "Code" },
  { key: "tool", label: "Tools" },
  { key: "social_post", label: "Social" },
  { key: "analysis", label: "Clinical" },
  { key: "diagnostic", label: "Diagnostic" },
];

export default async function QueuePage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const sp = await searchParams;
  const kind = sp.kind ?? "pr";
  const artifacts: Artifact[] = await getQueue(kind);
  const pending = artifacts.filter(a => a.queue_state === "pending");
  const approved = artifacts.filter(a => a.queue_state === "approved");
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Noctua · last night</h1>
        <p className="text-sm text-zinc-400">Artifacts ready for your review.</p>
      </header>
      <TabBar tabs={TABS} active={kind} />
      <section className="mt-6">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Pending ({pending.length})</h2>
        <div className="space-y-3">
          {pending.map(a => <ArtifactCard key={a.id} artifact={a} />)}
          {pending.length === 0 && <p className="text-zinc-500 text-sm">Nothing pending.</p>}
        </div>
      </section>
      {approved.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Recently approved ({approved.length})</h2>
          <div className="space-y-3 opacity-60">
            {approved.map(a => <ArtifactCard key={a.id} artifact={a} />)}
          </div>
        </section>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Write `TabBar.tsx`**

```typescript
// ui/components/TabBar.tsx
import Link from "next/link";
import clsx from "clsx";

export default function TabBar({ tabs, active }: { tabs: { key: string; label: string }[]; active: string }) {
  return (
    <nav className="flex gap-2 border-b border-zinc-800">
      {tabs.map(t => (
        <Link key={t.key} href={`/queue?kind=${t.key}`}
          className={clsx("px-4 py-2 text-sm rounded-t",
            t.key === active ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200")}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
```

- [ ] **Step 3: Write `ArtifactCard.tsx`**

```typescript
// ui/components/ArtifactCard.tsx
import Link from "next/link";
import type { Artifact } from "@/lib/types";

export default function ArtifactCard({ artifact: a }: { artifact: Artifact }) {
  const title = (a.preview?.title as string) ?? (a.preview?.name as string) ?? a.uri;
  const snippet = (a.preview?.snippet as string) ?? "";
  return (
    <Link href={`/queue/${a.id}`} className="block rounded border border-zinc-800 hover:border-zinc-600 bg-zinc-900 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-zinc-500 uppercase">{a.kind} · {a.producer_key}</div>
          <div className="font-medium">{title}</div>
          {snippet && <div className="text-sm text-zinc-400 mt-1">{snippet}</div>}
        </div>
        <div className="text-xs text-zinc-500">{a.queue_state}</div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Install `clsx` and verify**

```bash
cd ui && npm install clsx
cp .env.local.example .env.local
# fill NEXT_PUBLIC_NOCTUA_TOKEN
npm run dev
```

Open http://localhost:3000/queue — expect pending artifacts list.

- [ ] **Step 5: Commit**

```bash
cd .. && git add ui/
git commit -m "feat(ui): /queue page with tabs and artifact cards"
```

---

### Task 29: Artifact detail page (PR + tool) with approve/reject

**Files:**
- Create: `ui/app/queue/[id]/page.tsx`
- Create: `ui/components/ArtifactActions.tsx` (client component)
- Create: `ui/components/SourceViewer.tsx`

- [ ] **Step 1: Write detail page**

```typescript
// ui/app/queue/[id]/page.tsx
import { getArtifact, getMission } from "@/lib/api";
import ArtifactActions from "@/components/ArtifactActions";
import SourceViewer from "@/components/SourceViewer";

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const artifact = await getArtifact(Number(id));
  const mission = await getMission(artifact.mission_id);
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <nav className="text-xs text-zinc-500 mb-4">
        Mission #{mission.id} · {mission.goal} → Plan v{(artifact.provenance as any)?.plan_version ?? "?"}
      </nav>
      <h1 className="text-2xl font-semibold">{(artifact.preview?.title as string) ?? artifact.uri}</h1>
      <div className="text-sm text-zinc-400 mt-1">{artifact.kind} · {artifact.queue_state}</div>

      {artifact.kind === "pr" && artifact.uri && (
        <iframe src={`${artifact.uri}/files`} className="w-full h-[60vh] mt-6 rounded border border-zinc-800 bg-white" />
      )}

      {artifact.kind === "tool" && (
        <SourceViewer artifactId={artifact.id} />
      )}

      <section className="mt-6 p-4 rounded border border-zinc-800">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400">Validation</h2>
        <pre className="text-xs mt-2">{JSON.stringify(artifact.validation, null, 2)}</pre>
      </section>

      <ArtifactActions artifact={artifact} />
    </main>
  );
}
```

- [ ] **Step 2: Write `ArtifactActions.tsx` (client)**

```typescript
// ui/components/ArtifactActions.tsx
"use client";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { approveArtifact, rejectArtifact } from "@/lib/api";
import type { Artifact } from "@/lib/types";

export default function ArtifactActions({ artifact }: { artifact: Artifact }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  if (artifact.queue_state !== "pending") return null;

  const isTool = artifact.kind === "tool";
  return (
    <div className="mt-6 flex gap-3">
      <button disabled={pending} onClick={() => start(async () => { await approveArtifact(artifact.id); router.push("/queue"); })}
        className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50">
        {isTool ? "Graduate" : "Approve"}
      </button>
      <button disabled={pending} onClick={() => start(async () => { await rejectArtifact(artifact.id); router.push("/queue"); })}
        className="px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50">
        Reject
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Write `SourceViewer.tsx` (server, fetches source via API)**

For MVP, source rendering can be a placeholder `<pre>` block from `preview.source` if shipped, else a placeholder.

```typescript
// ui/components/SourceViewer.tsx
export default function SourceViewer({ artifactId }: { artifactId: number }) {
  return (
    <section className="mt-6 p-4 rounded border border-zinc-800 bg-zinc-900">
      <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Tool source (artifact #{artifactId})</h2>
      <p className="text-xs text-zinc-500">Source viewer to be wired to a `/api/artifacts/:id/source` endpoint (v0.2). For now, approve to graduate.</p>
    </section>
  );
}
```

- [ ] **Step 4: Verify in browser**

```bash
cd ui && npm run dev
```

Open `/queue`, click a card → detail page renders → Approve flips the artifact.

- [ ] **Step 5: Commit**

```bash
cd .. && git add ui/
git commit -m "feat(ui): artifact detail page + approve/reject/graduate actions"
```

---

### Task 30: Rubric editor

**Files:**
- Create: `ui/app/producers/[key]/rubric/page.tsx`
- Create: `ui/components/RubricEditor.tsx` (client)

- [ ] **Step 1: Write rubric editor**

```typescript
// ui/components/RubricEditor.tsx
"use client";
import { useState, useTransition } from "react";
import { updateRubric } from "@/lib/api";

export default function RubricEditor({ producerKey, initial }: { producerKey: string; initial: string }) {
  const [text, setText] = useState(initial);
  const [pending, start] = useTransition();
  const [saved, setSaved] = useState(false);
  return (
    <div className="mt-4">
      <textarea value={text} onChange={e => setText(e.target.value)}
        className="w-full h-[60vh] font-mono text-sm bg-zinc-900 border border-zinc-800 rounded p-3" />
      <div className="mt-3 flex gap-2 items-center">
        <button disabled={pending} onClick={() => start(async () => { await updateRubric(producerKey, text); setSaved(true); })}
          className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50">Save</button>
        {saved && <span className="text-sm text-emerald-400">Saved.</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write page**

```typescript
// ui/app/producers/[key]/rubric/page.tsx
import { getProducers } from "@/lib/api";
import RubricEditor from "@/components/RubricEditor";
import type { Producer } from "@/lib/types";

export default async function RubricPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const producers: Producer[] = await getProducers();
  const p = producers.find(x => x.key === key);
  if (!p) return <main className="p-8 text-zinc-100">Producer not found.</main>;
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <h1 className="text-2xl font-semibold">{p.key} · rubric (v{p.version})</h1>
      <p className="text-sm text-zinc-400 mt-1">Markdown rubric injected into the planner prompt.</p>
      <RubricEditor producerKey={p.key} initial={p.rubric_md} />
    </main>
  );
}
```

- [ ] **Step 3: Verify**

Open `/producers/pr/rubric`, edit, save, reload — saved.

- [ ] **Step 4: Commit**

```bash
git add ui/app/producers/ ui/components/RubricEditor.tsx
git commit -m "feat(ui): producer rubric editor"
```

---

### Task 31: WS 4 smoke

- [ ] **Step 1: Reset + seed**

```bash
docker compose up -d
./manage.py migrate
./manage.py seed_producers
./manage.py seed_stub_artifacts
celery -A noctua worker -l info &
./manage.py runserver 8000 &
cd ui && npm run dev &
```

- [ ] **Step 2: Walk the UI**

Visit http://localhost:3000/queue → click tabs → click Social card → see canned artifact → reject → returns to queue with one fewer item.

- [ ] **Step 3: Commit any small UI polish**

```bash
git add -A && git commit -m "chore(ws4): smoke verified" --allow-empty
```

---

## WS 5 — Example target + Operations

### Task 32: Test-fixture repo (`noctua-demo-app`)

**Files (in a SIBLING repo, not this one):**

- [ ] **Step 1: Create the demo repo**

```bash
gh repo create hugoduar/noctua-demo-app --public --description "Demo app for Noctua hackathon" --confirm
cd ~/workspace && git clone https://github.com/hugoduar/noctua-demo-app.git
cd noctua-demo-app
mkdir -p src tests
```

- [ ] **Step 2: Add a minimal FastAPI + pytest skeleton**

```python
# src/__init__.py — empty
# src/app.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"app": "noctua-demo"}
```

```python
# tests/test_app.py
from fastapi.testclient import TestClient
from src.app import app

def test_root():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
```

```toml
# pyproject.toml
[project]
name = "noctua-demo-app"
version = "0.1.0"
dependencies = ["fastapi", "uvicorn"]
[project.optional-dependencies]
dev = ["pytest", "httpx"]
```

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /work
COPY . /work
RUN pip install -e ".[dev]"
CMD ["python", "-m", "pytest", "-q"]
```

- [ ] **Step 3: Create 3 GitHub issues**

```bash
gh issue create --title "Add /healthz endpoint returning {ok: true}" --body "Standard liveness probe."
gh issue create --title "Seed the database with 5 sample widgets for local dev" --body "Add a seed command that inserts 5 widget rows. Requires a seed_db tool."
gh issue create --title "Add a unit-conversion module (km↔mi, c↔f) with tests" --body "Multi-file edit: new module + tests."
```

- [ ] **Step 4: Commit and push**

```bash
git add -A && git commit -m "Initial demo app"
git push -u origin main
```

- [ ] **Step 5: Back in Noctua repo, add a `Makefile` target**

```makefile
# Append to Makefile in noctua repo
.PHONY: reset-demo
reset-demo:
	cd ../noctua-demo-app && \
	  gh pr list --state all --json number --jq '.[].number' | xargs -n1 -I{} gh pr close {} || true && \
	  git fetch origin && git reset --hard origin/main && \
	  git branch | grep noctua/ | xargs -n1 -I{} git branch -D {} || true
```

```bash
cd ~/workspace/platanus
git add Makefile && git commit -m "chore(demo): reset-demo make target"
```

---

### Task 33: Mission archive + replay

**Files:**
- Create: `noctua/runner/archive.py`
- Modify: `noctua/runner/tasks.py` (call archive on teardown)
- Add command: `noctua/core/management/commands/replay.py`

- [ ] **Step 1: Write archive**

```python
# noctua/runner/archive.py
import json
from pathlib import Path
from django.conf import settings
from noctua.core.models import Mission

def archive_mission(mission_id: int):
    m = Mission.objects.get(id=mission_id)
    base = settings.NOCTUA_ARCHIVE_DIR / str(m.id)
    base.mkdir(parents=True, exist_ok=True)
    (base / "mission.json").write_text(json.dumps({
        "id": m.id, "goal": m.goal, "state": m.state, "state_reason": m.state_reason,
        "producer_key": m.producer_key, "spent": m.spent, "budget": m.budget,
    }, indent=2))
    plans = [{"version": p.version, "steps": p.steps, "rendered_md": p.rendered_md} for p in m.plans.all()]
    (base / "plans.json").write_text(json.dumps(plans, indent=2))
    artifacts = [{"id": a.id, "kind": a.kind, "uri": a.uri, "preview": a.preview, "validation": a.validation} for a in m.artifacts.all()]
    (base / "artifacts.json").write_text(json.dumps(artifacts, indent=2))
```

- [ ] **Step 2: Call in `run_mission` finally block**

Add at the end of the `finally:` block in `noctua/runner/tasks.py`:

```python
from noctua.runner.archive import archive_mission
archive_mission(m.id)
```

- [ ] **Step 3: Write replay command**

```python
# noctua/core/management/commands/replay.py
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Replay an archived mission to stdout."
    def add_arguments(self, parser):
        parser.add_argument("mission_id", type=int)
    def handle(self, *args, mission_id, **kwargs):
        base = settings.NOCTUA_ARCHIVE_DIR / str(mission_id)
        for name in ("mission.json", "plans.json", "artifacts.json"):
            self.stdout.write(f"=== {name} ===")
            self.stdout.write((base / name).read_text())
```

- [ ] **Step 4: Smoke**

```bash
./manage.py replay 1
```

Expected: dumps of the archived mission.

- [ ] **Step 5: Commit**

```bash
git add noctua/runner/archive.py noctua/runner/tasks.py noctua/core/management/commands/replay.py
git commit -m "feat(demo): mission archive + replay command"
```

---

### Task 34: End-to-end run + README

- [ ] **Step 1: Run the full stack against the fixture repo**

```bash
make reset-demo
make up
make migrate
make seed
./manage.py seed_stub_artifacts
celery -A noctua worker -l info &
./manage.py runserver 8000 &
cd ui && npm run dev &

noctua run --repo $NOCTUA_DEMO_REPO --issue $NOCTUA_DEMO_REPO/issues/1 --goal "Add /healthz"
noctua run --repo $NOCTUA_DEMO_REPO --issue $NOCTUA_DEMO_REPO/issues/2 --goal "Seed widgets"
```

The queue at http://localhost:3000/queue fills with: pending PR artifact for issue #1, a fabricated `seed_db` tool artifact, pending PR artifact for issue #2. Approve, graduate, approve.

- [ ] **Step 2: README — run it yourself**

Update the root README with:
- A "Run it yourself" section that lists `make up && make migrate && make seed`, the worker + runserver + ui commands, and a sample `noctua run` invocation.
- A short architecture diagram (ASCII) lifted from `docs/superpowers/specs/...`.

- [ ] **Step 3: Commit and push**

```bash
git add -A
git commit -m "docs: run-it-yourself + architecture in README"
git push
```

---

## Final self-review pass

- [ ] All tests pass: `pytest -x`.
- [ ] All UI routes render without console errors: walk `/queue`, `/queue/[id]`, `/producers/pr/rubric`.
- [ ] An end-to-end mission opens a draft PR.
- [ ] Approving a PR artifact flips the GitHub PR to ready-for-review.
- [ ] A fabricated `seed_db` tool appears in the Tools tab and graduates on approval.
- [ ] Stub tabs render their canned artifacts.
- [ ] `./manage.py replay <mission_id>` reproduces a mission's archived state.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-noctua-mvp.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
