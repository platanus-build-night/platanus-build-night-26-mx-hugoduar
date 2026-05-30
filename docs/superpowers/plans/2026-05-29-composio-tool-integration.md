# Composio Tool Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Composio's managed-tools service into Noctua as a fourth `ToolRegistry` source so the four currently-stubbed producers (`social_post`, `clinical_analysis`, `diagnostic`, `cad`) can do real external work (LinkedIn / X / Bluesky / Notion / Linear / Slack / Gmail / Drive) without disturbing the plan→execute spine the PR producer relies on.

**Architecture:** A thin `ComposioClient` wraps the `composio` Python SDK; a `ComposioToolAdapter` synthesizes `ToolEntry` instances on demand for `composio:<TOOLKIT>.<ACTION>` names. A new `Connection` table tracks per-toolkit OAuth state (single shared `user_id`). A new `external_tools=True` producer lane in `run_mission` runs plans without booting a sandbox. Pre-flight check at mission creation refuses missions whose required toolkits are not connected.

**Tech Stack:** Python 3.12, Django 5 + django-ninja, Celery, Anthropic SDK, Composio Python SDK, Next.js 16 (UI). Tests use pytest-django with mocked Composio SDK.

**Spec:** `docs/superpowers/specs/2026-05-29-composio-tool-integration-design.md` — read it first.

**Conventions reused from this codebase:**
- Every test file starts with `pytestmark = pytest.mark.django_db` when it touches the ORM.
- Tests mock the Composio SDK at the wrapper boundary; no test hits the real Composio API.
- `noctua/integrations/composio.py` is the only module that imports the `composio` SDK.
- The runtime guard pattern from `noctua/runner/llm.py:call_with_cache` ("API key empty? raise loudly with a hint") is mirrored in `ComposioClient.__init__`.
- Tool names follow `composio:<TOOLKIT>.<ACTION>` exactly (uppercase, dot separator). Example: `composio:LINKEDIN.LINKEDIN_CREATE_POST`.
- Per CLAUDE.md: client-side UI calls go through `ui/lib/api.ts:call()` — never bare `fetch().json()`.

---

## File Structure

**New files:**
- `noctua/integrations/__init__.py` — empty package marker
- `noctua/integrations/composio.py` — `ComposioClient`, `ComposioToolAdapter`, return types
- `noctua/core/migrations/<auto>_connection.py` — `Connection` model migration (auto-generated)
- `noctua/producers/external/__init__.py` — re-exports the four new producer classes
- `noctua/producers/external/base.py` — `ExternalToolsProducer` base class
- `noctua/producers/external/social_post.py` — `SocialPostProducer`
- `noctua/producers/external/clinical_analysis.py` — `ClinicalAnalysisProducer`
- `noctua/producers/external/diagnostic.py` — `DiagnosticProducer`
- `noctua/producers/external/cad.py` — `CADProducer`
- `noctua/producers/external/rubrics/social_post.md`
- `noctua/producers/external/rubrics/clinical_analysis.md`
- `noctua/producers/external/rubrics/diagnostic.md`
- `noctua/producers/external/rubrics/cad.md`
- `noctua/producers/external/prompts/clinical_analysis.md` — Claude system prompt for the edit step
- `noctua/producers/external/prompts/diagnostic.md`
- `noctua/producers/external/prompts/cad.md`
- `noctua/producers/external/prompts/social_post.md` — used to draft post text from `goal`
- `ui/app/connections/page.tsx`
- `tests/integrations/__init__.py`
- `tests/integrations/test_composio_client.py`
- `tests/integrations/test_composio_adapter.py`
- `tests/core/test_connection_model.py`
- `tests/core/test_connections_api.py`
- `tests/core/test_mission_preflight.py`
- `tests/tools/test_registry_composio.py`
- `tests/runner/test_external_tools_lane.py`
- `tests/runner/test_executor_no_sandbox.py`
- `tests/producers/test_social_post_producer.py`
- `tests/producers/test_clinical_analysis_producer.py`
- `tests/producers/test_diagnostic_producer.py`
- `tests/producers/test_cad_producer.py`
- `tests/test_composio_cli.py`

**Modified files:**
- `pyproject.toml` — add `composio>=0.7` to `dependencies`; re-point producer entry points
- `.env.example` — add `COMPOSIO_API_KEY=`
- `noctua/settings.py` — add `COMPOSIO_API_KEY` and `COMPOSIO_USER_ID`
- `noctua/core/models.py` — add `Connection` model
- `noctua/core/api.py` — add `/api/connections*` endpoints, add pre-flight check in `create_mission`, add `/api/producers/toolkits`
- `noctua/core/schemas.py` — `ConnectionOut`, `ConnectionInitiateOut`
- `noctua/core/management/commands/seed_producers.py` — re-point rubric paths
- `noctua/tools/registry.py` — 4th branch in `lookup`, `producer` kwarg in `all_available`
- `noctua/runner/executor.py` — accept `sandbox=None`, raise on `exec` without sandbox
- `noctua/runner/tasks.py` — `external_tools` branch
- `noctua/runner/planner.py` — thread producer into `all_available`; render composio actions in prompt
- `noctua/runner/prompts/plan.md` — mention `composio:*` tools
- `noctua/cli.py` — `composio` command group

**Deleted (last task):**
- `noctua/producers/stub/` — entire directory (replaced by `external/`)

---

## Task Index

1. Settings + dependency + .env wiring
2. `ComposioClient` wrapper (tests first)
3. `ComposioToolAdapter` (tests first)
4. `Connection` Django model + migration
5. `Connection` REST API (list / initiate / refresh / disconnect)
6. Connections UI page
7. Registry: 4th branch + `producer` kwarg in `all_available`
8. Executor: accept `sandbox=None`
9. `external_tools` lane in `run_mission`
10. Producer base class `ExternalToolsProducer` with manifest fields
11. Pre-flight check in `POST /api/missions`
12. `/api/producers/toolkits` for the UI
13. `social_post` producer
14. `clinical_analysis` producer
15. `diagnostic` producer
16. `cad` producer
17. `seed_producers` rubric paths + entry points re-point + delete `stub/`
18. CLI: `noctua composio connect / list / disconnect`
19. Final integration verification

---

## Task 1: Settings + dependency + .env wiring

**Files:**
- Modify: `pyproject.toml`
- Modify: `noctua/settings.py:51-55`
- Modify: `.env.example`

- [ ] **Step 1: Add the SDK dependency**

Open `pyproject.toml` and add to the `dependencies` array (between `"anthropic>=0.40",` and `"click>=8.1",`):

```toml
  "composio>=0.7",
```

- [ ] **Step 2: Add settings keys**

In `noctua/settings.py`, after `GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")` add:

```python
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID = os.environ.get("COMPOSIO_USER_ID", "noctua_default")
```

- [ ] **Step 3: Update .env.example**

Append to `.env.example`:

```
# Composio managed-tools (required for social_post / clinical_analysis / diagnostic / cad producers)
COMPOSIO_API_KEY=
# Optional override; defaults to "noctua_default". One Composio user_id per Noctua instance.
# COMPOSIO_USER_ID=noctua_default
```

- [ ] **Step 4: Install**

Run:
```bash
pip install -e ".[dev]"
```
Expected: installs `composio` and its transitive deps; no other changes.

- [ ] **Step 5: Smoke-import the SDK**

Run:
```bash
python -c "from composio import Composio; print('ok')"
```
Expected: prints `ok`. If the import path differs in the installed version, note the actual top-level (e.g. `from composio_core import Composio`) — every subsequent task references `from composio import Composio`; update it consistently in the wrapper if needed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml noctua/settings.py .env.example
git commit -m "deps: add composio SDK and config keys"
```

---

## Task 2: `ComposioClient` wrapper

This is the only module in the project that imports the `composio` SDK. Everything else calls this wrapper.

**Files:**
- Create: `noctua/integrations/__init__.py` (empty)
- Create: `noctua/integrations/composio.py`
- Create: `tests/integrations/__init__.py` (empty)
- Create: `tests/integrations/test_composio_client.py`

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p noctua/integrations tests/integrations
touch noctua/integrations/__init__.py tests/integrations/__init__.py
```

- [ ] **Step 2: Write the failing client tests**

Create `tests/integrations/test_composio_client.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from noctua.integrations.composio import (
    ComposioClient,
    ExecutionResult,
    ActionSpec,
    ConnectionInit,
    ComposioAuthError,
)


def test_init_raises_when_api_key_missing(settings):
    settings.COMPOSIO_API_KEY = ""
    with pytest.raises(RuntimeError, match="COMPOSIO_API_KEY is empty"):
        ComposioClient()


def test_init_constructs_sdk_when_api_key_present(settings):
    settings.COMPOSIO_API_KEY = "test-key"
    with patch("noctua.integrations.composio.Composio") as sdk:
        c = ComposioClient()
        sdk.assert_called_once_with(api_key="test-key")
        assert c._sdk is sdk.return_value


def test_execute_returns_successful_result(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.execute.return_value = MagicMock(
            successful=True, data={"url": "https://x/123"}, error=None
        )
        c = ComposioClient()
        r = c.execute(slug="LINKEDIN_CREATE_POST", arguments={"text": "hi"}, user_id="u")
        assert isinstance(r, ExecutionResult)
        assert r.successful is True
        assert r.data == {"url": "https://x/123"}
        assert r.error == ""


def test_execute_returns_failed_result_with_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.execute.return_value = MagicMock(
            successful=False, data=None, error="rate limited"
        )
        c = ComposioClient()
        r = c.execute(slug="X", arguments={}, user_id="u")
        assert r.successful is False
        assert r.error == "rate limited"


def test_execute_translates_auth_error(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        # Simulate the SDK raising whatever it raises for expired auth.
        # We catch any exception whose str contains 'auth' (case-insensitive)
        # or whose class name contains 'Auth' and re-raise as ComposioAuthError.
        sdk.return_value.tools.execute.side_effect = RuntimeError("AuthExpired: token revoked")
        c = ComposioClient()
        with pytest.raises(ComposioAuthError):
            c.execute(slug="X", arguments={}, user_id="u")


def test_get_action_spec_caches_per_slug(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.tools.get.return_value = MagicMock(
            name="LINKEDIN_CREATE_POST",
            description="Create a LinkedIn post",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        )
        c = ComposioClient()
        s1 = c.get_action_spec("LINKEDIN_CREATE_POST")
        s2 = c.get_action_spec("LINKEDIN_CREATE_POST")
        assert isinstance(s1, ActionSpec)
        assert s1.input_schema == {"type": "object", "properties": {"text": {"type": "string"}}}
        # Cached — SDK called only once
        sdk.return_value.tools.get.assert_called_once()
        assert s1 is s2


def test_initiate_connection_returns_redirect_url_and_id(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.connected_accounts.initiate.return_value = MagicMock(
            redirect_url="https://oauth.example/x", id="conn_abc"
        )
        c = ComposioClient()
        r = c.initiate_connection(toolkit="LINKEDIN", user_id="u")
        assert isinstance(r, ConnectionInit)
        assert r.redirect_url == "https://oauth.example/x"
        assert r.composio_conn_id == "conn_abc"


def test_fetch_connection_status_returns_status_string(settings):
    settings.COMPOSIO_API_KEY = "k"
    with patch("noctua.integrations.composio.Composio") as sdk:
        sdk.return_value.connected_accounts.get.return_value = MagicMock(status="ACTIVE")
        c = ComposioClient()
        assert c.fetch_connection_status("conn_abc") == "ACTIVE"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/integrations/test_composio_client.py -v
```
Expected: import error / ModuleNotFoundError for `noctua.integrations.composio`.

- [ ] **Step 4: Implement the wrapper**

Create `noctua/integrations/composio.py`:

```python
"""Single seam between Noctua and the Composio Python SDK.

Everything Composio-shaped flows through this module. The rest of Noctua sees
plain dataclasses (ExecutionResult, ActionSpec, ConnectionInit) and one custom
exception (ComposioAuthError) — never the raw SDK types. If the SDK shape
changes in a future release, only this file changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from django.conf import settings

# Import surface: only this module imports `composio` directly.
from composio import Composio  # type: ignore[import-untyped]


# ---- Return types -----------------------------------------------------------


@dataclass
class ExecutionResult:
    successful: bool
    data: Any
    error: str


@dataclass
class ActionSpec:
    name: str
    description: str
    input_schema: dict


@dataclass
class ConnectionInit:
    redirect_url: str
    composio_conn_id: str


class ComposioAuthError(Exception):
    """Raised when a Composio call fails because of expired / revoked auth."""


def _looks_like_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    cls = type(exc).__name__.lower()
    return "auth" in msg or "expired" in msg or "auth" in cls


# ---- Client -----------------------------------------------------------------


class ComposioClient:
    """Thin, process-wide wrapper around the composio SDK.

    Per-process: not thread-local. The action-spec cache lives on this instance;
    construct one per worker process and reuse.
    """

    def __init__(self):
        if not settings.COMPOSIO_API_KEY:
            raise RuntimeError(
                "COMPOSIO_API_KEY is empty. The Celery worker / API process did "
                "not get the env loaded — restart after "
                "`set -a; source .env; set +a` or ensure .env exists at the project root."
            )
        self._sdk = Composio(api_key=settings.COMPOSIO_API_KEY)
        self._spec_cache: dict[str, ActionSpec] = {}

    def execute(self, *, slug: str, arguments: dict, user_id: str) -> ExecutionResult:
        try:
            raw = self._sdk.tools.execute(slug=slug, arguments=arguments, user_id=user_id)
        except Exception as e:
            if _looks_like_auth_error(e):
                raise ComposioAuthError(str(e)) from e
            raise
        return ExecutionResult(
            successful=bool(getattr(raw, "successful", False)),
            data=getattr(raw, "data", None),
            error=getattr(raw, "error", None) or "",
        )

    def get_action_spec(self, slug: str) -> ActionSpec:
        if slug in self._spec_cache:
            return self._spec_cache[slug]
        raw = self._sdk.tools.get(slug=slug)
        spec = ActionSpec(
            name=getattr(raw, "name", slug),
            description=getattr(raw, "description", "") or "",
            input_schema=getattr(raw, "input_schema", {}) or {},
        )
        self._spec_cache[slug] = spec
        return spec

    def initiate_connection(self, *, toolkit: str, user_id: str) -> ConnectionInit:
        raw = self._sdk.connected_accounts.initiate(toolkit=toolkit, user_id=user_id)
        return ConnectionInit(
            redirect_url=getattr(raw, "redirect_url", "") or "",
            composio_conn_id=getattr(raw, "id", "") or "",
        )

    def fetch_connection_status(self, composio_conn_id: str) -> str:
        raw = self._sdk.connected_accounts.get(composio_conn_id)
        return getattr(raw, "status", "UNKNOWN") or "UNKNOWN"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/integrations/test_composio_client.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/integrations tests/integrations
git commit -m "feat(composio): client wrapper around composio SDK"
```

---

## Task 3: `ComposioToolAdapter`

The adapter synthesizes `ToolEntry` instances for `composio:<TOOLKIT>.<ACTION>` names and provides the per-producer listing the registry needs.

**Files:**
- Modify: `noctua/integrations/composio.py` (append `ComposioToolAdapter`)
- Create: `tests/integrations/test_composio_adapter.py`

- [ ] **Step 1: Write the failing adapter tests**

Create `tests/integrations/test_composio_adapter.py`:

```python
import pytest
from unittest.mock import MagicMock
from noctua.integrations.composio import (
    ComposioToolAdapter,
    ComposioAuthError,
    ExecutionResult,
    ActionSpec,
)
from noctua.tools.base import ToolResult


@pytest.fixture
def fake_client():
    c = MagicMock()
    c.get_action_spec.return_value = ActionSpec(
        name="LINKEDIN_CREATE_POST",
        description="",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    )
    return c


def test_lookup_returns_tool_entry_with_composio_status(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    assert entry.name == "composio:LINKEDIN.LINKEDIN_CREATE_POST"
    assert entry.status == "composio"
    assert entry.signature == {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }


def test_lookup_caches_entries(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    e1 = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    e2 = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    assert e1 is e2


def test_lookup_raises_on_malformed_name(fake_client):
    adapter = ComposioToolAdapter(client=fake_client)
    with pytest.raises(ValueError, match="malformed composio tool name"):
        adapter.lookup("composio:NO_DOT_HERE")
    with pytest.raises(ValueError, match="malformed composio tool name"):
        adapter.lookup("LINKEDIN.CREATE_POST")  # missing prefix


def test_call_returns_tool_result_on_success(fake_client, settings):
    settings.COMPOSIO_USER_ID = "noctua_default"
    fake_client.execute.return_value = ExecutionResult(
        successful=True, data={"url": "https://x/1"}, error=""
    )
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({"text": "hello"}, sandbox=None)
    assert isinstance(r, ToolResult)
    assert r.ok is True
    assert r.value == {"url": "https://x/1"}
    fake_client.execute.assert_called_once_with(
        slug="LINKEDIN_CREATE_POST",
        arguments={"text": "hello"},
        user_id="noctua_default",
    )


def test_call_returns_failed_tool_result_on_sdk_error(fake_client):
    fake_client.execute.return_value = ExecutionResult(
        successful=False, data=None, error="rate limited"
    )
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert r.error == "rate limited"


@pytest.mark.django_db
def test_call_flips_connection_to_expired_on_auth_error(fake_client):
    from noctua.core.models import Connection  # will exist after Task 4
    Connection.objects.create(
        toolkit="LINKEDIN", status="active", composio_conn_id="c1",
    )
    fake_client.execute.side_effect = ComposioAuthError("token revoked")
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert r.error == "connection_expired:LINKEDIN"
    Connection.objects.get(toolkit="LINKEDIN")  # still there
    assert Connection.objects.get(toolkit="LINKEDIN").status == "expired"


def test_call_returns_failed_result_on_unexpected_exception(fake_client):
    fake_client.execute.side_effect = ValueError("boom")
    adapter = ComposioToolAdapter(client=fake_client)
    entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
    r = entry.callable({}, sandbox=None)
    assert r.ok is False
    assert "boom" in r.error


@pytest.mark.django_db
def test_list_actions_for_producer_returns_entries_for_active_toolkits_only(fake_client):
    from noctua.core.models import Connection
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    Connection.objects.create(toolkit="TWITTER", status="expired", composio_conn_id="c2")
    # BLUESKY: no row at all

    class FakeProducer:
        composio_actions = {
            "LINKEDIN": ["LINKEDIN_CREATE_POST"],
            "TWITTER": ["TWITTER_CREATE_TWEET"],
            "BLUESKY": ["BLUESKY_CREATE_POST"],
        }

    adapter = ComposioToolAdapter(client=fake_client)
    entries = adapter.list_actions_for_producer(FakeProducer())
    names = {e.name for e in entries}
    assert names == {"composio:LINKEDIN.LINKEDIN_CREATE_POST"}


@pytest.mark.django_db
def test_list_actions_for_producer_returns_empty_when_no_composio_actions(fake_client):
    class FakeProducer:
        pass  # no composio_actions attr
    adapter = ComposioToolAdapter(client=fake_client)
    assert adapter.list_actions_for_producer(FakeProducer()) == []
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/integrations/test_composio_adapter.py -v
```
Expected: ImportError on `ComposioToolAdapter` (and `Connection` for the two django_db tests — those will fail more loudly until Task 4 lands; that's fine, those two we'll re-run after Task 4).

- [ ] **Step 3: Implement the adapter**

Append to `noctua/integrations/composio.py`:

```python
# ---- Adapter ---------------------------------------------------------------


class ComposioToolAdapter:
    """Synthesizes ToolEntry instances for composio:<TOOLKIT>.<ACTION> names.

    Usage:
        adapter = ComposioToolAdapter()  # constructs its own ComposioClient
        entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
        result = entry.callable({"text": "hi"}, sandbox=None)
    """

    def __init__(self, client: ComposioClient | None = None):
        self._client = client or ComposioClient()
        self._entry_cache: dict[str, "ToolEntry"] = {}

    def lookup(self, name: str) -> "ToolEntry":
        from noctua.tools.base import ToolEntry, ToolResult  # local to avoid cycle

        if name in self._entry_cache:
            return self._entry_cache[name]
        if not name.startswith("composio:"):
            raise ValueError(f"malformed composio tool name (missing prefix): {name}")
        body = name.removeprefix("composio:")
        if "." not in body:
            raise ValueError(f"malformed composio tool name (need TOOLKIT.ACTION): {name}")
        toolkit, action = body.split(".", 1)
        spec = self._client.get_action_spec(action)

        client = self._client  # capture for closure

        def call(args: dict, sandbox=None) -> ToolResult:
            try:
                r = client.execute(
                    slug=action,
                    arguments=args,
                    user_id=settings.COMPOSIO_USER_ID,
                )
            except ComposioAuthError as e:
                from noctua.core.models import Connection
                Connection.objects.filter(toolkit=toolkit).update(
                    status="expired", last_error=str(e),
                )
                return ToolResult(ok=False, error=f"connection_expired:{toolkit}")
            except Exception as e:
                return ToolResult(ok=False, error=str(e))
            if r.successful:
                return ToolResult(ok=True, value=r.data)
            return ToolResult(ok=False, error=r.error or "composio_execute_failed")

        entry = ToolEntry(
            name=name,
            signature=spec.input_schema,
            status="composio",
            callable=call,
            source_path="",  # not on disk
        )
        self._entry_cache[name] = entry
        return entry

    def list_actions_for_producer(self, producer) -> list["ToolEntry"]:
        from noctua.core.models import Connection

        actions_map: dict[str, list[str]] = getattr(producer, "composio_actions", {}) or {}
        if not actions_map:
            return []
        active_toolkits = set(
            Connection.objects.filter(
                toolkit__in=list(actions_map.keys()), status="active",
            ).values_list("toolkit", flat=True)
        )
        entries = []
        for toolkit, actions in actions_map.items():
            if toolkit not in active_toolkits:
                continue
            for action in actions:
                entries.append(self.lookup(f"composio:{toolkit}.{action}"))
        return entries
```

- [ ] **Step 4: Run non-django tests**

```bash
pytest tests/integrations/test_composio_adapter.py -v -k "not flips and not active_toolkits and not no_composio_actions"
```
Expected: 5 non-`django_db` tests pass. The 3 `django_db` tests will fail because `Connection` doesn't exist yet — that's fine; Task 4 brings them green.

- [ ] **Step 5: Commit**

```bash
git add noctua/integrations/composio.py tests/integrations/test_composio_adapter.py
git commit -m "feat(composio): tool adapter synthesizing ToolEntry for composio:* names"
```

---

## Task 4: `Connection` Django model + migration

**Files:**
- Modify: `noctua/core/models.py`
- Create: `noctua/core/migrations/<auto>_connection.py` (auto-generated)
- Create: `tests/core/test_connection_model.py`

- [ ] **Step 1: Write the failing model test**

Create `tests/core/test_connection_model.py`:

```python
import pytest
from django.db import IntegrityError
from noctua.core.models import Connection

pytestmark = pytest.mark.django_db


def test_create_connection_with_defaults():
    c = Connection.objects.create(
        toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc",
    )
    assert c.connected_at is None
    assert c.last_error == ""
    assert c.created_at is not None


def test_toolkit_is_unique():
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    with pytest.raises(IntegrityError):
        Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c2")


def test_status_choices_cover_lifecycle():
    # All four states are accepted at the field level (no validators reject them).
    for state in ("active", "expired", "revoked", "pending"):
        Connection.objects.create(toolkit=f"TK_{state}", status=state, composio_conn_id="x").full_clean()
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/core/test_connection_model.py -v
```
Expected: `ImportError` on `Connection`.

- [ ] **Step 3: Add the model**

In `noctua/core/models.py`, after the `MISSION_STATES` line at the top add:

```python
CONNECTION_STATUSES = [(s, s) for s in ["active", "expired", "revoked", "pending"]]
```

At the end of the file (after `Signal`) add:

```python
class Connection(models.Model):
    """Per-toolkit OAuth state for the single shared Composio user_id."""

    toolkit = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=CONNECTION_STATUSES, default="pending")
    composio_conn_id = models.CharField(max_length=128)
    connected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: Generate the migration**

```bash
./manage.py makemigrations core
```
Expected: creates `noctua/core/migrations/000X_connection.py`.

- [ ] **Step 5: Apply the migration**

```bash
./manage.py migrate
```
Expected: `Applying core.000X_connection... OK`.

- [ ] **Step 6: Run model + earlier adapter tests**

```bash
pytest tests/core/test_connection_model.py tests/integrations/test_composio_adapter.py -v
```
Expected: all 3 model tests pass; all 8 adapter tests now pass (including the previously-failing `django_db` ones).

- [ ] **Step 7: Commit**

```bash
git add noctua/core/models.py noctua/core/migrations tests/core/test_connection_model.py
git commit -m "feat: Connection model for per-toolkit OAuth state"
```

---

## Task 5: `Connection` REST API

Endpoints for the Connections UI page and the CLI.

**Files:**
- Modify: `noctua/core/schemas.py`
- Modify: `noctua/core/api.py`
- Create: `tests/core/test_connections_api.py`

- [ ] **Step 1: Add output schemas**

Open `noctua/core/schemas.py` (read it first to match existing style) and append:

```python
class ConnectionOut(Schema):
    toolkit: str
    status: str
    composio_conn_id: str
    connected_at: str | None = None
    last_error: str = ""


class ConnectionInitiateOut(Schema):
    toolkit: str
    redirect_url: str
    composio_conn_id: str
    status: str
```

(If `noctua/core/schemas.py` doesn't import `Schema` from `ninja`, add `from ninja import Schema` at top.)

- [ ] **Step 2: Write the failing API tests**

Create `tests/core/test_connections_api.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from noctua.core.models import Connection

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_headers(settings):
    settings.NOCTUA_API_TOKEN = "test-token"
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}


def test_list_connections_empty(auth_headers):
    r = Client().get("/api/connections", **auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_connections_returns_all_rows(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    Connection.objects.create(toolkit="NOTION", status="pending", composio_conn_id="c2")
    r = Client().get("/api/connections", **auth_headers)
    assert r.status_code == 200
    bodies = {row["toolkit"]: row for row in r.json()}
    assert set(bodies.keys()) == {"LINKEDIN", "NOTION"}
    assert bodies["LINKEDIN"]["status"] == "active"


def test_initiate_creates_pending_row_and_returns_oauth_url(auth_headers, settings):
    settings.COMPOSIO_USER_ID = "noctua_default"
    with patch("noctua.core.api.ComposioClient") as Client_cls:
        Client_cls.return_value.initiate_connection.return_value = MagicMock(
            redirect_url="https://oauth.example/x", composio_conn_id="conn_new"
        )
        r = Client().post("/api/connections/LINKEDIN/initiate", **auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["toolkit"] == "LINKEDIN"
    assert body["redirect_url"] == "https://oauth.example/x"
    assert body["composio_conn_id"] == "conn_new"
    assert body["status"] == "pending"
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "pending"
    assert row.composio_conn_id == "conn_new"


def test_initiate_replaces_existing_row_for_same_toolkit(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="expired", composio_conn_id="old")
    with patch("noctua.core.api.ComposioClient") as Client_cls:
        Client_cls.return_value.initiate_connection.return_value = MagicMock(
            redirect_url="https://oauth.example/x", composio_conn_id="conn_new"
        )
        r = Client().post("/api/connections/LINKEDIN/initiate", **auth_headers)
    assert r.status_code == 201
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.composio_conn_id == "conn_new"
    assert row.status == "pending"
    assert row.last_error == ""


def test_refresh_flips_to_active_when_composio_reports_active(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc")
    with patch("noctua.core.api.ComposioClient") as Client_cls:
        Client_cls.return_value.fetch_connection_status.return_value = "ACTIVE"
        r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 200
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "active"
    assert row.connected_at is not None


def test_refresh_keeps_pending_when_composio_not_yet_active(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="pending", composio_conn_id="conn_abc")
    with patch("noctua.core.api.ComposioClient") as Client_cls:
        Client_cls.return_value.fetch_connection_status.return_value = "INITIATED"
        r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 200
    row = Connection.objects.get(toolkit="LINKEDIN")
    assert row.status == "pending"


def test_refresh_404_when_no_row(auth_headers):
    r = Client().post("/api/connections/LINKEDIN/refresh", **auth_headers)
    assert r.status_code == 404


def test_disconnect_flips_to_revoked(auth_headers):
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="conn_abc")
    r = Client().post("/api/connections/LINKEDIN/disconnect", **auth_headers)
    assert r.status_code == 200
    assert Connection.objects.get(toolkit="LINKEDIN").status == "revoked"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
pytest tests/core/test_connections_api.py -v
```
Expected: 404 on every endpoint (routes don't exist yet).

- [ ] **Step 4: Add the routes**

In `noctua/core/api.py`, near the top with the other imports add:

```python
from noctua.core.models import Connection
from noctua.integrations.composio import ComposioClient
from noctua.core.schemas import ConnectionOut, ConnectionInitiateOut
```

(If `noctua/core/schemas.py` doesn't re-export these, ensure they're imported wherever ninja needs them.)

Add this block after the existing producer endpoints (after `update_rubric`):

```python
# ---- Composio connections --------------------------------------------------


def _serialize_connection(c: Connection) -> dict:
    return {
        "toolkit": c.toolkit,
        "status": c.status,
        "composio_conn_id": c.composio_conn_id,
        "connected_at": c.connected_at.isoformat() if c.connected_at else None,
        "last_error": c.last_error,
    }


@api.get("/connections", response=list[ConnectionOut])
def list_connections(request):
    return [_serialize_connection(c) for c in Connection.objects.all().order_by("toolkit")]


@api.post("/connections/{toolkit}/initiate", response={201: ConnectionInitiateOut})
def initiate_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    client = ComposioClient()
    init = client.initiate_connection(toolkit=toolkit, user_id=settings.COMPOSIO_USER_ID)
    obj, _ = Connection.objects.update_or_create(
        toolkit=toolkit,
        defaults={
            "status": "pending",
            "composio_conn_id": init.composio_conn_id,
            "last_error": "",
            "connected_at": None,
        },
    )
    return 201, {
        "toolkit": obj.toolkit,
        "redirect_url": init.redirect_url,
        "composio_conn_id": obj.composio_conn_id,
        "status": obj.status,
    }


@api.post("/connections/{toolkit}/refresh", response=ConnectionOut)
def refresh_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    obj = get_object_or_404(Connection, toolkit=toolkit)
    client = ComposioClient()
    raw_status = client.fetch_connection_status(obj.composio_conn_id).upper()
    if raw_status == "ACTIVE":
        obj.status = "active"
        obj.connected_at = now()
        obj.last_error = ""
    elif raw_status in ("EXPIRED", "FAILED", "REVOKED"):
        obj.status = "expired"
    else:
        obj.status = "pending"
    obj.save(update_fields=["status", "connected_at", "last_error", "updated_at"])
    return _serialize_connection(obj)


@api.post("/connections/{toolkit}/disconnect", response=ConnectionOut)
def disconnect_connection(request, toolkit: str):
    toolkit = toolkit.upper()
    obj = get_object_or_404(Connection, toolkit=toolkit)
    obj.status = "revoked"
    obj.save(update_fields=["status", "updated_at"])
    return _serialize_connection(obj)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/core/test_connections_api.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add noctua/core/api.py noctua/core/schemas.py tests/core/test_connections_api.py
git commit -m "feat: REST API for Composio connections (list/initiate/refresh/disconnect)"
```

---

## Task 6: Connections UI page

**Files:**
- Create: `ui/app/connections/page.tsx`
- Modify: `ui/components/TabBar.tsx` (add "Connections" link)

**Conventions reminder:** All client-side API calls go through `ui/lib/api.ts:call()`. Tailwind 4 (no config file). Read `ui/AGENTS.md` first if unfamiliar.

- [ ] **Step 1: Read existing UI patterns**

```bash
cat ui/lib/api.ts
cat ui/components/TabBar.tsx
ls ui/app
```
Pick a sibling page (e.g. `ui/app/sandboxes/page.tsx`) to mirror its structure/styling.

- [ ] **Step 2: Create the page**

Create `ui/app/connections/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { call } from "@/lib/api";

type Connection = {
  toolkit: string;
  status: "active" | "expired" | "revoked" | "pending";
  composio_conn_id: string;
  connected_at: string | null;
  last_error: string;
};

type ProducerToolkits = {
  toolkits: string[]; // every toolkit referenced by any producer's required_ or optional_toolkits
};

export default function ConnectionsPage() {
  const [conns, setConns] = useState<Connection[]>([]);
  const [knownToolkits, setKnownToolkits] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const [c, t] = await Promise.all([
        call<Connection[]>("/api/connections"),
        call<ProducerToolkits>("/api/producers/toolkits"),
      ]);
      setConns(c);
      setKnownToolkits(t.toolkits);
    } catch (e: any) {
      setError(e.message ?? String(e));
    }
  }

  useEffect(() => { refresh(); }, []);

  const byToolkit = new Map(conns.map((c) => [c.toolkit, c]));

  async function initiate(toolkit: string) {
    setBusy(toolkit);
    try {
      const r = await call<{ redirect_url: string }>(
        `/api/connections/${toolkit}/initiate`, { method: "POST" }
      );
      window.open(r.redirect_url, "_blank", "noopener");
      await refresh();
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally { setBusy(null); }
  }

  async function refreshOne(toolkit: string) {
    setBusy(toolkit);
    try {
      await call(`/api/connections/${toolkit}/refresh`, { method: "POST" });
      await refresh();
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally { setBusy(null); }
  }

  async function disconnect(toolkit: string) {
    setBusy(toolkit);
    try {
      await call(`/api/connections/${toolkit}/disconnect`, { method: "POST" });
      await refresh();
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally { setBusy(null); }
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold mb-6">Connections</h1>
      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}
      <table className="w-full text-sm">
        <thead className="text-left text-neutral-500">
          <tr>
            <th className="py-2">Toolkit</th>
            <th className="py-2">Status</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {knownToolkits.map((tk) => {
            const c = byToolkit.get(tk);
            const status = c?.status ?? "not_connected";
            return (
              <tr key={tk} className="border-t border-neutral-200">
                <td className="py-3 font-mono">{tk}</td>
                <td className="py-3">
                  <span className={
                    status === "active" ? "text-green-700" :
                    status === "pending" ? "text-amber-700" :
                    status === "expired" ? "text-red-700" :
                    "text-neutral-500"
                  }>{status}</span>
                  {c?.last_error && (
                    <div className="text-xs text-neutral-500">{c.last_error}</div>
                  )}
                </td>
                <td className="py-3 text-right">
                  <button
                    disabled={busy === tk}
                    onClick={() => initiate(tk)}
                    className="rounded border px-2 py-1 mr-2"
                  >Connect</button>
                  {c && (
                    <>
                      <button
                        disabled={busy === tk}
                        onClick={() => refreshOne(tk)}
                        className="rounded border px-2 py-1 mr-2"
                      >Refresh</button>
                      {status === "active" && (
                        <button
                          disabled={busy === tk}
                          onClick={() => disconnect(tk)}
                          className="rounded border border-red-300 text-red-700 px-2 py-1"
                        >Disconnect</button>
                      )}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </main>
  );
}
```

- [ ] **Step 3: Add Connections tab to TabBar**

Open `ui/components/TabBar.tsx`. Find the array of tab definitions (it'll be something like `const tabs = [{href: "/queue", label: "Queue"}, ...]`). Add `{ href: "/connections", label: "Connections" }` at an appropriate position (after Sandboxes, before any settings).

- [ ] **Step 4: Smoke test in browser**

```bash
cd ui && npm run dev
```
Navigate to http://localhost:3000/connections. Expected:
- The page loads with an empty table (no toolkits registered yet — that comes after Task 13 lands `social_post`).
- Tab "Connections" appears in nav.
- No console errors.

If `/api/producers/toolkits` 404s, the page should render the error banner; that's expected until Task 12.

- [ ] **Step 5: Commit**

```bash
git add ui/app/connections ui/components/TabBar.tsx
git commit -m "feat(ui): Connections page (Composio toolkits status + actions)"
```

---

## Task 7: Registry: 4th branch + `producer` kwarg in `all_available`

**Files:**
- Modify: `noctua/tools/registry.py`
- Create: `tests/tools/test_registry_composio.py`

- [ ] **Step 1: Write the failing registry tests**

Create `tests/tools/test_registry_composio.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from noctua.tools.registry import ToolRegistry
from noctua.tools.base import ToolEntry

pytestmark = pytest.mark.django_db


def test_lookup_dispatches_composio_prefix_to_adapter():
    with patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        fake_entry = ToolEntry(name="composio:X.Y", signature={}, status="composio", callable=lambda a, s: None)
        Adapter.return_value.lookup.return_value = fake_entry
        reg = ToolRegistry()
        entry = reg.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST", current_mission_id=1)
    assert entry is fake_entry
    Adapter.return_value.lookup.assert_called_once_with(
        "composio:LINKEDIN.LINKEDIN_CREATE_POST"
    )


def test_lookup_falls_through_for_bundled_names():
    reg = ToolRegistry()
    entry = reg.lookup("read_file", current_mission_id=1)
    assert entry is not None
    assert entry.status == "hardcoded"


def test_all_available_includes_composio_actions_when_producer_passed():
    with patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        fake_entry = ToolEntry(name="composio:LINKEDIN.LINKEDIN_CREATE_POST", signature={}, status="composio", callable=lambda a, s: None)
        Adapter.return_value.list_actions_for_producer.return_value = [fake_entry]
        producer = MagicMock(composio_actions={"LINKEDIN": ["LINKEDIN_CREATE_POST"]})
        reg = ToolRegistry()
        entries = reg.all_available(current_mission_id=1, producer=producer)
    names = [e.name for e in entries]
    assert "composio:LINKEDIN.LINKEDIN_CREATE_POST" in names
    # bundled still included
    assert "read_file" in names


def test_all_available_without_producer_returns_no_composio_entries():
    reg = ToolRegistry()
    entries = reg.all_available(current_mission_id=1)
    assert not any(e.name.startswith("composio:") for e in entries)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/tools/test_registry_composio.py -v
```
Expected: `AttributeError: module 'noctua.tools.registry' has no attribute 'ComposioToolAdapter'` and/or `all_available` doesn't accept `producer` kwarg.

- [ ] **Step 3: Update the registry**

Replace `noctua/tools/registry.py` entirely with:

```python
# noctua/tools/registry.py
import importlib.util
from noctua.core.models import Tool
from noctua.tools.base import ToolEntry
from noctua.tools.bundled import BUNDLED
from noctua.integrations.composio import ComposioToolAdapter


class ToolRegistry:
    def __init__(self):
        self._bundled = {t.name: t for t in BUNDLED}
        self._composio = ComposioToolAdapter()

    def lookup(self, name: str, current_mission_id: int | None = None) -> ToolEntry | None:
        # 0. composio:* dispatches to the adapter (it constructs the SDK lazily on first use)
        if name.startswith("composio:"):
            return self._composio.lookup(name)
        # 1. graduated
        graduated = Tool.objects.filter(name=name, status="graduated").first()
        if graduated:
            return self._load_from_disk(graduated)
        # 2. hardcoded
        if name in self._bundled:
            return self._bundled[name]
        # 3. fabricated for THIS mission
        if current_mission_id:
            fab = Tool.objects.filter(
                name=name,
                status="fabricated_sandbox_only",
                fabricated_by_mission_id=current_mission_id,
            ).first()
            if fab:
                return self._load_from_disk(fab)
        return None

    def _load_from_disk(self, tool_row: Tool) -> ToolEntry:
        spec = importlib.util.spec_from_file_location(tool_row.name, tool_row.source_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return ToolEntry(
            name=tool_row.name, signature=tool_row.signature, status=tool_row.status,
            callable=mod.call, source_path=tool_row.source_path,
        )

    def all_available(self, current_mission_id: int | None = None, producer=None) -> list[ToolEntry]:
        entries = list(self._bundled.values())
        for row in Tool.objects.filter(status="graduated"):
            entries.append(self._load_from_disk(row))
        if current_mission_id:
            for row in Tool.objects.filter(
                status="fabricated_sandbox_only",
                fabricated_by_mission_id=current_mission_id,
            ):
                entries.append(self._load_from_disk(row))
        if producer is not None:
            entries.extend(self._composio.list_actions_for_producer(producer))
        return entries
```

**Note:** The adapter is constructed eagerly in `ToolRegistry.__init__`, which means every `ToolRegistry()` will attempt to construct a `ComposioClient` — which requires `COMPOSIO_API_KEY`. This will break existing tests that construct registries without the env var set.

To avoid that: make adapter construction lazy. Replace `__init__`:

```python
    def __init__(self):
        self._bundled = {t.name: t for t in BUNDLED}
        self._composio: ComposioToolAdapter | None = None

    def _composio_adapter(self) -> ComposioToolAdapter:
        if self._composio is None:
            self._composio = ComposioToolAdapter()
        return self._composio
```

And update `lookup`/`all_available` to call `self._composio_adapter().lookup(...)` / `self._composio_adapter().list_actions_for_producer(...)`.

Update the test patch target accordingly: tests patch `noctua.integrations.composio.ComposioToolAdapter` (where it's defined). Adjust the tests if needed:

```python
with patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
```
This works for both eager and lazy construction since the patch replaces the class-level reference. Keep the lazy pattern in the registry.

- [ ] **Step 4: Run new tests + existing registry tests**

```bash
pytest tests/tools/ -v
```
Expected: 4 new tests pass; existing 2 tests in `tests/tools/test_registry.py` still pass.

- [ ] **Step 5: Commit**

```bash
git add noctua/tools/registry.py tests/tools/test_registry_composio.py
git commit -m "feat: ToolRegistry dispatches composio:* to adapter; producer kwarg in all_available"
```

---

## Task 8: Executor accepts `sandbox=None`

**Files:**
- Modify: `noctua/runner/executor.py`
- Create: `tests/runner/test_executor_no_sandbox.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/runner/test_executor_no_sandbox.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from noctua.core.models import Mission, Plan
from noctua.runner.executor import execute_plan
from noctua.tools.base import ToolEntry, ToolResult

pytestmark = pytest.mark.django_db


def _budget():
    return {"max_tool_calls": 10, "max_tokens": 10_000, "max_wall_seconds": 60}


def test_execute_tool_step_without_sandbox_passes_none_to_callable():
    m = Mission.objects.create(goal="g", producer_key="social_post", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINKEDIN.LINKEDIN_CREATE_POST", "args": {"text": "hi"}},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    captured = {}
    def fake_call(args, sandbox):
        captured["args"] = args
        captured["sandbox"] = sandbox
        return ToolResult(ok=True, value={"url": "https://x/1"})
    fake_entry = ToolEntry(name="composio:LINKEDIN.LINKEDIN_CREATE_POST",
                           signature={}, status="composio", callable=fake_call)

    with patch("noctua.runner.executor.ToolRegistry") as Reg:
        Reg.return_value.lookup.return_value = fake_entry
        results = execute_plan(m, plan, sandbox=None)

    assert results[0]["status"] == "succeeded"
    assert captured["args"] == {"text": "hi"}
    assert captured["sandbox"] is None


def test_execute_exec_step_without_sandbox_raises():
    m = Mission.objects.create(goal="g", producer_key="social_post", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "exec",
         "payload": {"cmd": ["echo", "hi"]},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    results = execute_plan(m, plan, sandbox=None)
    # All retries fail the same way → step status is failed; result.error mentions sandbox.
    assert results[0]["status"] == "failed"
    assert "sandbox" in results[0]["result"]["error"].lower()


def test_execute_edit_step_without_sandbox_passes_none_to_producer():
    m = Mission.objects.create(goal="g", producer_key="clinical_analysis", budget=_budget())
    plan = Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "edit",
         "payload": {"goal": "analyze"},
         "status": "pending", "attempt": 0, "result": None},
    ], rendered_md="")

    captured = {}
    fake_producer = MagicMock()
    def fake_execute_step(step, sandbox, mission):
        captured["sandbox"] = sandbox
        return ToolResult(ok=True, value="ok")
    fake_producer.execute_step.side_effect = fake_execute_step

    results = execute_plan(m, plan, sandbox=None, producer=fake_producer)
    assert results[0]["status"] == "succeeded"
    assert captured["sandbox"] is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/runner/test_executor_no_sandbox.py -v
```
Expected: the `exec` test currently passes a `None.exec(...)` call which raises AttributeError, then retries, then fails — likely already fails the way the test wants. The `tool` and `edit` tests may already pass (the executor's existing code passes whatever `sandbox` it was given). Run to confirm — if any test fails, the change in Step 3 is necessary.

- [ ] **Step 3: Tighten the executor's exec-step error**

Open `noctua/runner/executor.py`. The current behavior for `kind: "exec"` with `sandbox=None` raises `AttributeError: 'NoneType' object has no attribute 'exec'` which is opaque. Replace the `elif step["kind"] == "exec":` block with:

```python
                elif step["kind"] == "exec":
                    if sandbox is None:
                        raise RuntimeError(
                            "exec step requires a sandbox; "
                            "external_tools producers must not emit kind:'exec' steps"
                        )
                    r = sandbox.exec(step["payload"]["cmd"], timeout=step["payload"].get("timeout", 60))
                    step["result"] = {"ok": r.exit_code == 0, "value": r.stdout, "error": r.stderr}
                    step["status"] = "succeeded" if r.exit_code == 0 else "failed"
```

No other changes — the `tool` and `edit` branches already pass `sandbox` through opaquely.

- [ ] **Step 4: Run tests**

```bash
pytest tests/runner/test_executor_no_sandbox.py tests/runner/test_executor.py -v
```
Expected: 3 new tests pass; existing executor test still passes.

- [ ] **Step 5: Commit**

```bash
git add noctua/runner/executor.py tests/runner/test_executor_no_sandbox.py
git commit -m "feat(executor): accept sandbox=None; clear error on exec step without sandbox"
```

---

## Task 9: `external_tools` lane in `run_mission`

**Files:**
- Modify: `noctua/runner/tasks.py`
- Modify: `noctua/runner/planner.py` (thread `producer` through to `all_available`)
- Create: `tests/runner/test_external_tools_lane.py`

- [ ] **Step 1: Write the failing lane test**

Create `tests/runner/test_external_tools_lane.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Plan, Artifact
from noctua.runner.tasks import run_mission

pytestmark = pytest.mark.django_db


CANNED_PLAN = '{"steps":[{"step_id":"s1","kind":"tool","payload":{"name":"composio:LINKEDIN.LINKEDIN_CREATE_POST","args":{"text":"hi"}}}],"rendered_md":"x"}'


@pytest.fixture
def external_producer():
    """A minimal producer with external_tools=True, registered in the cache."""
    from noctua.tools.base import ToolResult
    from noctua.producers import registry as preg

    class _P:
        key = "test_external"
        kind = "social_post"
        external_tools = True
        content_only = False
        required_toolkits = ["LINKEDIN"]
        optional_toolkits: list[str] = []
        composio_actions = {"LINKEDIN": ["LINKEDIN_CREATE_POST"]}

        def execute_step(self, step, sandbox, mission):
            return ToolResult(ok=True)

        def finalize(self, mission, sandbox=None):
            return Artifact.objects.create(
                mission=mission, producer_key=self.key, kind=self.kind,
                uri=f"draft://{self.key}/{mission.id}", queue_state="pending",
            )

        def on_approve(self, a): pass
        def on_promote(self, a): pass

    p = _P()
    preg._cache["test_external"] = p
    yield p
    preg._cache.pop("test_external", None)


def test_external_tools_lane_skips_sandbox(external_producer):
    Producer.objects.create(key="test_external", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="test_external", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})

    planner_resp = MagicMock()
    planner_resp.content = [MagicMock(text=CANNED_PLAN)]
    planner_resp.usage = MagicMock(input_tokens=10, output_tokens=10)

    # Fake adapter so composio:* lookups don't need real Composio
    from noctua.tools.base import ToolEntry, ToolResult
    fake_entry = ToolEntry(
        name="composio:LINKEDIN.LINKEDIN_CREATE_POST", signature={}, status="composio",
        callable=lambda a, s: ToolResult(ok=True, value={"url": "https://x/1"}),
    )

    with patch("noctua.runner.planner.call_with_cache", return_value=planner_resp), \
         patch("noctua.runner.tasks.Sandbox") as Sandbox, \
         patch("noctua.tools.registry.ComposioToolAdapter") as Adapter:
        Adapter.return_value.lookup.return_value = fake_entry
        Adapter.return_value.list_actions_for_producer.return_value = [fake_entry]
        run_mission(m.id)
        Sandbox.assert_not_called()  # boot/teardown never happens

    m.refresh_from_db()
    assert m.state == "succeeded"
    assert Artifact.objects.filter(mission=m).exists()


def test_external_tools_lane_archives_on_failure(external_producer, monkeypatch):
    Producer.objects.create(key="test_external", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="g", producer_key="test_external", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})

    with patch("noctua.runner.tasks.plan_for_mission", side_effect=RuntimeError("planner_broke")):
        run_mission(m.id)

    m.refresh_from_db()
    assert m.state == "failed"
    assert "planner_broke" in m.state_reason
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/runner/test_external_tools_lane.py -v
```
Expected: Sandbox **is** called (no external_tools branch yet) — `Sandbox.assert_not_called()` raises.

- [ ] **Step 3: Add the lane in tasks.py**

In `noctua/runner/tasks.py`, modify `run_mission`. After the `content_only` block (the existing `if getattr(producer, "content_only", False):` branch) and before the `# ---- existing full lifecycle ... ----` comment, insert:

```python
    # External-tools producers (social_post, clinical_analysis, diagnostic, cad after migration)
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
```

- [ ] **Step 4: Update planner to accept and use `producer`**

In `noctua/runner/planner.py`, change `plan_for_mission` signature:

```python
def plan_for_mission(mission: Mission, producer=None) -> tuple[Plan, int]:
    """Return (Plan, total_tokens_used).

    `producer` is forwarded to `ToolRegistry.all_available` so producer-specific
    composio tools appear in the planner's tool catalog. If None, only bundled
    and graduated tools are exposed.
    """
```

Then, inside the function, render an "Available tools" section in the user message so the planner knows what `composio:*` names are valid. Replace the `user = f"..."` block with:

```python
    from noctua.tools.registry import ToolRegistry
    registry = ToolRegistry()
    available = registry.all_available(current_mission_id=mission.id, producer=producer)
    tool_catalog = "\n".join(
        f"- {e.name} ({e.status}): {e.signature}" for e in available
    )

    user = f"""Mission:
Goal: {mission.goal}
Repo: {mission.repo_url}
Issue: {mission.issue_url}
Inputs: {json.dumps(mission.inputs)}
Success criteria: {mission.success_criteria}

Producer rubric:
{rubric}

Available tools (use these exact names in step payload.name):
{tool_catalog}
"""
```

This works for both the PR producer (gets bundled-only tools) and external producers (gets composio entries too).

- [ ] **Step 5: Update planner's caller in the PR lane**

In `noctua/runner/tasks.py`, in the existing PR lane, change:
```python
plan, tokens = plan_for_mission(m)
```
to:
```python
plan, tokens = plan_for_mission(m, producer=producer)
```

- [ ] **Step 6: Update `noctua/runner/prompts/plan.md`**

Append to `plan.md`:

```
External-tool steps:
- "composio:<TOOLKIT>.<ACTION>" names (when listed in Available tools) are calls to
  an external SaaS via Composio's managed gateway. They run outside the sandbox;
  do NOT wrap them in bash -lc. The `payload.args` are JSON arguments matching
  the action's input_schema.
- For external_tools producers, every step should be `kind: "tool"` with a
  composio:* name, OR `kind: "edit"` for a producer-driven Claude step
  (no `kind: "exec"`).
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/runner/test_external_tools_lane.py tests/runner/test_lifecycle.py tests/runner/test_planner.py -v
```
Expected: new lane tests pass; existing lifecycle and planner tests still pass (the PR producer gets composio entries=none since its `composio_actions` is empty).

- [ ] **Step 8: Commit**

```bash
git add noctua/runner/tasks.py noctua/runner/planner.py noctua/runner/prompts/plan.md tests/runner/test_external_tools_lane.py
git commit -m "feat: external_tools lane in run_mission; planner exposes composio actions"
```

---

## Task 10: Producer base class `ExternalToolsProducer`

**Files:**
- Create: `noctua/producers/external/__init__.py`
- Create: `noctua/producers/external/base.py`

- [ ] **Step 1: Create the package**

```bash
mkdir -p noctua/producers/external/rubrics noctua/producers/external/prompts
touch noctua/producers/external/__init__.py
```

- [ ] **Step 2: Write the base class**

Create `noctua/producers/external/base.py`:

```python
"""Base class for producers that drive external SaaS tools via Composio.

These producers:
- declare required and optional toolkits (the API pre-flights `required`)
- declare a composio_actions map (toolkit → list of action slugs) exposed to the planner
- use the external_tools=True lane in run_mission (no sandbox boot)
- handle `kind: "edit"` steps by running a pure Claude call (no shell, sandbox=None)
"""

from __future__ import annotations

import json
from pathlib import Path
from noctua.core.models import Mission, Artifact, Producer
from noctua.runner.llm import call_with_cache, PLANNER_MODEL
from noctua.runner.budget import increment_spent
from noctua.tools.base import ToolResult


class ExternalToolsProducer:
    """Subclass and set the class attributes. See SocialPostProducer for an example."""

    # Lifecycle hints for run_mission
    external_tools: bool = True
    content_only: bool = False

    # Manifest
    key: str = ""
    kind: str = ""              # one of ARTIFACT_KINDS
    required_toolkits: list[str] = []   # at-least-one semantics
    optional_toolkits: list[str] = []   # not pre-flight-checked
    composio_actions: dict[str, list[str]] = {}   # planner-visible catalog

    # Prompt for the Claude edit step (relative to noctua/producers/external/prompts/)
    edit_prompt_file: str = ""

    # ---- Lifecycle hooks (no-op defaults) ----

    def on_approve(self, artifact: Artifact) -> None: pass
    def on_promote(self, artifact: Artifact) -> None: pass

    # ---- Edit step: Claude call without a sandbox ----

    def execute_step(self, step: dict, sandbox, mission: Mission) -> ToolResult:
        """Default edit-step handler: read the edit prompt, ask Claude, return text.

        The result.value is the raw Claude text; subclasses may override to parse
        it differently. `sandbox` is always None for external_tools producers.
        """
        if not self.edit_prompt_file:
            return ToolResult(ok=False, error=f"{self.key}: no edit_prompt_file set")
        prompts_dir = Path(__file__).parent / "prompts"
        system = (prompts_dir / self.edit_prompt_file).read_text()
        context = step.get("payload", {})
        # Roll prior tool-step results into the user message so Claude has them.
        prior = self._collect_prior_results(mission, step)
        user = (
            f"Step goal:\n{context.get('goal', '')}\n\n"
            f"Step context:\n{json.dumps(context, indent=2)}\n\n"
            f"Prior step results:\n{json.dumps(prior, indent=2)}\n"
        )
        try:
            resp = call_with_cache(
                messages=[{"role": "user", "content": user}],
                system=system, model=PLANNER_MODEL, max_tokens=4000,
            )
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
        try:
            increment_spent(mission.id, tokens=resp.usage.input_tokens + resp.usage.output_tokens)
        except Exception:
            pass
        text = resp.content[0].text
        return ToolResult(ok=True, value=text)

    def _collect_prior_results(self, mission: Mission, current_step: dict) -> list[dict]:
        plan = mission.plans.order_by("-version").first()
        if not plan:
            return []
        out = []
        for s in plan.steps:
            if s.get("step_id") == current_step.get("step_id"):
                break
            if s.get("status") == "succeeded":
                out.append({"step_id": s["step_id"], "result": s.get("result", {}).get("value")})
        return out

    # ---- Finalize: persist Artifact ----

    def finalize(self, mission: Mission, sandbox=None) -> Artifact:
        """Default: bundle all step results into the Artifact preview."""
        plan = mission.plans.order_by("-version").first()
        step_summary = []
        if plan:
            for s in plan.steps:
                step_summary.append({
                    "step_id": s.get("step_id"),
                    "kind": s.get("kind"),
                    "status": s.get("status"),
                    "result": s.get("result", {}).get("value"),
                })
        return Artifact.objects.create(
            mission=mission,
            producer_key=self.key,
            kind=self.kind,
            uri=self._artifact_uri(mission, step_summary),
            preview=self._artifact_preview(mission, step_summary),
            provenance={"generated_by": self.key, "external_tools": True},
            validation={"steps": len(step_summary)},
            queue_state="pending",
        )

    def _artifact_uri(self, mission: Mission, steps: list[dict]) -> str:
        return f"draft://{self.key}/{mission.id}"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        return {"goal": mission.goal, "steps": steps}
```

- [ ] **Step 3: Smoke import**

```bash
python -c "from noctua.producers.external.base import ExternalToolsProducer; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add noctua/producers/external
git commit -m "feat(producers): ExternalToolsProducer base for composio-driven producers"
```

---

## Task 11: Pre-flight check in `POST /api/missions`

**Files:**
- Modify: `noctua/core/api.py:18-36`
- Create: `tests/core/test_mission_preflight.py`

- [ ] **Step 1: Write the failing preflight tests**

Create `tests/core/test_mission_preflight.py`:

```python
import pytest
import json
from unittest.mock import patch
from django.test import Client
from noctua.core.models import Mission, Connection

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_headers(settings):
    settings.NOCTUA_API_TOKEN = "test-token"
    return {"HTTP_AUTHORIZATION": "Bearer test-token"}


def _make_external_producer_in_cache(key="social_post", required=("LINKEDIN", "TWITTER", "BLUESKY")):
    from noctua.producers import registry as preg

    class _P:
        external_tools = True
        content_only = False
        required_toolkits = list(required)
        optional_toolkits: list[str] = []
        composio_actions = {tk: [f"{tk}_DO_THING"] for tk in required}
    preg._cache[key] = _P()


def test_create_mission_rejected_when_no_required_toolkit_connected(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN", "TWITTER", "BLUESKY"))
    payload = {
        "goal": "post about the launch",
        "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    r = Client().post("/api/missions",
                      data=json.dumps(payload),
                      content_type="application/json", **auth_headers)
    assert r.status_code == 400
    body = r.json()
    assert body.get("error") == "missing_connections"
    assert set(body.get("toolkits", [])) == {"LINKEDIN", "TWITTER", "BLUESKY"}
    assert Mission.objects.count() == 0


def test_create_mission_accepted_when_at_least_one_required_toolkit_active(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN", "TWITTER", "BLUESKY"))
    Connection.objects.create(toolkit="LINKEDIN", status="active", composio_conn_id="c1")
    payload = {
        "goal": "post about the launch",
        "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    # Patch run_mission so we don't actually fire it during the API test
    with patch("noctua.core.api.run_mission") as run:
        r = Client().post("/api/missions",
                          data=json.dumps(payload),
                          content_type="application/json", **auth_headers)
    assert r.status_code == 201
    assert Mission.objects.count() == 1
    run.delay.assert_called_once()


def test_create_mission_rejected_when_only_expired_connection_present(auth_headers):
    _make_external_producer_in_cache("social_post", ("LINKEDIN",))
    Connection.objects.create(toolkit="LINKEDIN", status="expired", composio_conn_id="c1")
    payload = {
        "goal": "x", "producer_key": "social_post",
        "inputs": {}, "success_criteria": "", "domain": "social",
        "repo_url": "", "issue_url": "", "auto_act": False,
    }
    r = Client().post("/api/missions",
                      data=json.dumps(payload),
                      content_type="application/json", **auth_headers)
    assert r.status_code == 400


def test_create_mission_skips_preflight_for_pr_producer(auth_headers):
    # PR producer has no required_toolkits; pre-flight should be a no-op.
    payload = {
        "goal": "fix the bug", "producer_key": "pr",
        "inputs": {}, "success_criteria": "", "domain": "code",
        "repo_url": "https://github.com/x/y", "issue_url": "", "auto_act": False,
    }
    with patch("noctua.core.api.run_mission"):
        r = Client().post("/api/missions",
                          data=json.dumps(payload),
                          content_type="application/json", **auth_headers)
    assert r.status_code == 201
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/core/test_mission_preflight.py -v
```
Expected: missions get created (status 201) even when no connections — the preflight doesn't exist yet. The first three tests fail.

- [ ] **Step 3: Add the preflight to `create_mission`**

In `noctua/core/api.py`, locate `create_mission` (around line 18). Add the import at the top if missing:

```python
from ninja.errors import HttpError
```

(ninja exports HttpError that produces a JSON body. If a different pattern is already in use in this file for 400 responses, mirror it instead — check `noctua/core/api.py` to confirm.)

Also import:
```python
from noctua.producers.registry import get_producer
```
(already imported — confirm; if not, add).

Replace the body of `create_mission`:

```python
@api.post("/missions", response={201: MissionOut})
def create_mission(request, payload: MissionCreate):
    from noctua.runner.tasks import run_mission  # local import to avoid Celery at import time
    # Pre-flight: producer's required_toolkits must each be reachable
    # via at least one active Connection. (Any one toolkit in the list suffices —
    # see spec §5 "alternatives, any of which suffices".)
    try:
        producer = get_producer(payload.producer_key)
    except LookupError as e:
        raise HttpError(400, f"unknown producer: {payload.producer_key}") from e
    required = list(getattr(producer, "required_toolkits", []) or [])
    if required:
        active = set(Connection.objects.filter(
            toolkit__in=required, status="active",
        ).values_list("toolkit", flat=True))
        if not active:
            # Use a Django JsonResponse so the body structure matches the test
            from django.http import JsonResponse
            return JsonResponse(
                {"error": "missing_connections", "toolkits": required},
                status=400,
            )
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
    m.refresh_from_db()
    return 201, m
```

**Important:** if ninja's response declaration `response={201: MissionOut}` rejects the 400 JsonResponse, switch to `response={201: MissionOut, 400: dict}` so ninja schema-validates both.

- [ ] **Step 4: Run preflight + existing mission API tests**

```bash
pytest tests/core/test_mission_preflight.py tests/core/test_mission_api.py -v
```
Expected: all 4 new tests pass. The pre-existing flaky `test_create_mission` may still flake (it hits real Docker + Anthropic per CLAUDE.md note); that's not a regression.

- [ ] **Step 5: Commit**

```bash
git add noctua/core/api.py tests/core/test_mission_preflight.py
git commit -m "feat(api): pre-flight check rejecting missions whose required toolkits aren't connected"
```

---

## Task 12: `/api/producers/toolkits` for the UI

**Files:**
- Modify: `noctua/core/api.py`
- Add test to: `tests/core/test_producer_api.py` (extend existing file)

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_producer_api.py`:

```python
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

    preg._cache["a"] = A()
    preg._cache["b"] = B()
    try:
        from django.test import Client
        r = Client().get("/api/producers/toolkits",
                         HTTP_AUTHORIZATION="Bearer t")
        assert r.status_code == 200
        # Only toolkits referenced by producers currently in the cache, deduped, sorted.
        assert sorted(r.json()["toolkits"]) == ["GMAIL", "LINKEDIN", "NOTION", "TWITTER"]
    finally:
        preg._cache.pop("a", None)
        preg._cache.pop("b", None)
```

(Add `import pytest` to the top if not already present.)

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/core/test_producer_api.py::test_producers_toolkits_returns_union_of_required_and_optional -v
```
Expected: 404.

- [ ] **Step 3: Add the endpoint**

In `noctua/core/api.py`, after `list_producers`:

```python
@api.get("/producers/toolkits")
def list_producer_toolkits(request):
    """Union of every required and optional toolkit across producers currently
    resolvable via the registry cache. Used by the Connections UI."""
    from noctua.producers import registry as preg
    toolkits: set[str] = set()
    for producer in preg._cache.values():
        toolkits.update(getattr(producer, "required_toolkits", []) or [])
        toolkits.update(getattr(producer, "optional_toolkits", []) or [])
    return {"toolkits": sorted(toolkits)}
```

**Note on cache:** `preg._cache` only contains producers that have been resolved this process. To populate it for the UI's first load, the API process needs to have called `get_producer(key)` for every entry-point at least once. A clean way: warm the cache at API startup. Add to `noctua/core/api.py` after the `api = NinjaAPI(...)` line:

```python
def _warm_producer_cache():
    from importlib.metadata import entry_points
    from noctua.producers.registry import get_producer
    for ep in entry_points(group="noctua.producers"):
        try:
            get_producer(ep.name)
        except Exception:
            pass  # producer with broken import — surface separately

_warm_producer_cache()
```

This runs once at module import. Cheap and avoids a chicken-and-egg with the cache.

- [ ] **Step 4: Run tests**

```bash
pytest tests/core/test_producer_api.py -v
```
Expected: new test passes; existing tests unaffected.

- [ ] **Step 5: Commit**

```bash
git add noctua/core/api.py tests/core/test_producer_api.py
git commit -m "feat(api): /producers/toolkits enumerates toolkits referenced by registered producers"
```

---

## Task 13: `social_post` producer

**Files:**
- Create: `noctua/producers/external/social_post.py`
- Create: `noctua/producers/external/rubrics/social_post.md`
- Create: `noctua/producers/external/prompts/social_post.md`
- Create: `tests/producers/test_social_post_producer.py`

- [ ] **Step 1: Write the failing producer test**

Create `tests/producers/test_social_post_producer.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from noctua.core.models import Mission, Producer, Connection, Plan, Artifact

pytestmark = pytest.mark.django_db


def _budget():
    return {"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60}


def test_social_post_manifest():
    from noctua.producers.external.social_post import SocialPostProducer
    p = SocialPostProducer()
    assert p.key == "social_post"
    assert p.kind == "social_post"
    assert p.external_tools is True
    assert set(p.required_toolkits) == {"LINKEDIN", "TWITTER", "BLUESKY"}
    assert "LINKEDIN" in p.composio_actions
    assert "LINKEDIN_CREATE_POST" in p.composio_actions["LINKEDIN"]


def test_social_post_finalize_records_post_urls_in_artifact_preview():
    from noctua.producers.external.social_post import SocialPostProducer
    Producer.objects.create(key="social_post", kind="social_post", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="launch tweet", producer_key="social_post", budget=_budget())
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINKEDIN.LINKEDIN_CREATE_POST", "args": {"text": "hi"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"url": "https://linkedin.com/p/1"}, "error": ""}},
        {"step_id": "s2", "kind": "tool",
         "payload": {"name": "composio:TWITTER.TWITTER_CREATE_TWEET", "args": {"text": "hi"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"url": "https://x.com/p/2"}, "error": ""}},
    ], rendered_md="")

    p = SocialPostProducer()
    a = p.finalize(m, sandbox=None)
    assert a.kind == "social_post"
    assert a.queue_state == "pending"
    posted = a.preview.get("posted_urls", [])
    assert "https://linkedin.com/p/1" in posted
    assert "https://x.com/p/2" in posted
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/producers/test_social_post_producer.py -v
```
Expected: ImportError on `SocialPostProducer`.

- [ ] **Step 3: Write the producer**

Create `noctua/producers/external/social_post.py`:

```python
from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class SocialPostProducer(ExternalToolsProducer):
    key = "social_post"
    kind = "social_post"
    required_toolkits = ["LINKEDIN", "TWITTER", "BLUESKY"]
    optional_toolkits: list[str] = []
    composio_actions = {
        "LINKEDIN": ["LINKEDIN_CREATE_POST"],
        "TWITTER":  ["TWITTER_CREATE_TWEET"],
        "BLUESKY":  ["BLUESKY_CREATE_POST"],
    }
    edit_prompt_file = "social_post.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        posted_urls = []
        for s in steps:
            if s.get("status") != "succeeded":
                continue
            value = s.get("result") or {}
            if isinstance(value, dict) and "url" in value:
                posted_urls.append(value["url"])
        return {
            "goal": mission.goal,
            "posted_urls": posted_urls,
            "steps": steps,
        }
```

- [ ] **Step 4: Write the rubric**

Create `noctua/producers/external/rubrics/social_post.md`:

```
You are drafting a social media post.

Inputs:
- `goal` (required): the topic / idea to post about. Can include voice/tone hints.
- `inputs.platforms` (optional): a list like ["LINKEDIN", "TWITTER"]. Default: all connected.

For each chosen, connected platform, emit one `kind: "tool"` step using the
platform's composio action (e.g. `composio:LINKEDIN.LINKEDIN_CREATE_POST`).
The `payload.args` must match the action's input schema. For text-only posts,
`{"text": "<the post body>"}` is enough.

If you want to vary the wording per platform (Twitter's 280-char limit, LinkedIn's
formal voice), emit an `kind: "edit"` step first that asks Claude to draft the
per-platform versions, then reference its result in the tool steps.

Plan length: 1–4 steps. Always end after the last tool step — no validation step
needed; the action returning successful is the validation.
```

- [ ] **Step 5: Write the edit prompt (for optional per-platform drafting)**

Create `noctua/producers/external/prompts/social_post.md`:

```
You are drafting variations of a single social media post for multiple platforms.

Output a JSON object: {"LINKEDIN": "...", "TWITTER": "...", "BLUESKY": "..."}.
Only include keys for platforms requested in the step goal.

Constraints:
- TWITTER: <= 280 chars
- LINKEDIN: professional voice, 1–3 short paragraphs
- BLUESKY: <= 300 chars, casual voice

Return only the JSON.
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/producers/test_social_post_producer.py -v
```
Expected: 2 tests pass.

- [ ] **Step 7: Commit**

```bash
git add noctua/producers/external/social_post.py noctua/producers/external/rubrics/social_post.md noctua/producers/external/prompts/social_post.md tests/producers/test_social_post_producer.py
git commit -m "feat(producers): social_post — real LinkedIn/X/Bluesky via Composio"
```

---

## Task 14: `clinical_analysis` producer

**Files:**
- Create: `noctua/producers/external/clinical_analysis.py`
- Create: `noctua/producers/external/rubrics/clinical_analysis.md`
- Create: `noctua/producers/external/prompts/clinical_analysis.md`
- Create: `tests/producers/test_clinical_analysis_producer.py`

- [ ] **Step 1: Write the test**

Create `tests/producers/test_clinical_analysis_producer.py`:

```python
import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_clinical_analysis_manifest():
    from noctua.producers.external.clinical_analysis import ClinicalAnalysisProducer
    p = ClinicalAnalysisProducer()
    assert p.key == "clinical_analysis"
    assert p.kind == "analysis"
    assert p.required_toolkits == ["NOTION"]
    assert p.optional_toolkits == ["GMAIL"]
    assert "NOTION_FETCH_PAGE" in p.composio_actions["NOTION"]
    assert "NOTION_CREATE_PAGE" in p.composio_actions["NOTION"]


def test_clinical_analysis_finalize_includes_analysis_uri_in_artifact():
    from noctua.producers.external.clinical_analysis import ClinicalAnalysisProducer
    Producer.objects.create(key="clinical_analysis", kind="analysis", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="analyze patient X", producer_key="clinical_analysis", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:NOTION.NOTION_FETCH_PAGE", "args": {"page_id": "p1"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"content": "notes..."}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "summarize"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "analysis text", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:NOTION.NOTION_CREATE_PAGE", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"page_url": "https://notion.so/p/new"}, "error": ""}},
    ], rendered_md="")

    p = ClinicalAnalysisProducer()
    a = p.finalize(m, sandbox=None)
    assert a.kind == "analysis"
    assert a.preview["analysis_url"] == "https://notion.so/p/new"
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/producers/test_clinical_analysis_producer.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write the producer**

Create `noctua/producers/external/clinical_analysis.py`:

```python
from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class ClinicalAnalysisProducer(ExternalToolsProducer):
    key = "clinical_analysis"
    kind = "analysis"
    required_toolkits = ["NOTION"]
    optional_toolkits = ["GMAIL"]
    composio_actions = {
        "NOTION": ["NOTION_FETCH_PAGE", "NOTION_CREATE_PAGE", "NOTION_APPEND_BLOCK"],
        "GMAIL":  ["GMAIL_SEND_EMAIL"],
    }
    edit_prompt_file = "clinical_analysis.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        analysis_url = ""
        email_sent_to = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if not v:
                continue
            if "page_url" in v:
                analysis_url = v["page_url"]
            if "to" in v and "subject" in v:
                email_sent_to = v["to"]
        return {
            "goal": mission.goal,
            "analysis_url": analysis_url,
            "email_sent_to": email_sent_to,
            "steps": steps,
        }
```

- [ ] **Step 4: Write the rubric**

Create `noctua/producers/external/rubrics/clinical_analysis.md`:

```
You analyze clinical notes stored in Notion and return a written analysis to the
patient's chart.

Inputs:
- `goal` (required): natural-language directive (e.g. "summarize the last 3 visits
  for patient X, highlight any flagged symptoms"). May include a Notion page ID
  or URL.
- `inputs.recipient_email` (optional): if present and GMAIL is connected, also
  email the analysis to this address.

Plan shape:
1. `composio:NOTION.NOTION_FETCH_PAGE` to load the source content.
2. `kind: "edit"` step asking Claude to write the analysis using the fetched
   content. The edit step's result.value is the analysis text.
3. `composio:NOTION.NOTION_CREATE_PAGE` with the analysis as a child of the
   source page (use the source page_id as parent).
4. Optionally `composio:GMAIL.GMAIL_SEND_EMAIL` if `inputs.recipient_email` is
   present and GMAIL is in the available tools.

Reference prior step results via `inputs.<step_id>` in your reasoning; the
executor inlines them when running the edit step.
```

- [ ] **Step 5: Write the edit prompt**

Create `noctua/producers/external/prompts/clinical_analysis.md`:

```
You are a clinical analyst. Read the source content from "Prior step results"
and write a structured analysis suitable for a patient chart.

Output format (markdown):
## Summary
<2-3 sentences>

## Findings
- <bullet>

## Recommended next steps
- <bullet>

Be conservative: never invent labs or measurements. If the source lacks data for
a section, write "Insufficient data in source." Do not include disclaimers.
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/producers/test_clinical_analysis_producer.py -v
```
Expected: both tests pass.

- [ ] **Step 7: Commit**

```bash
git add noctua/producers/external/clinical_analysis.py noctua/producers/external/rubrics/clinical_analysis.md noctua/producers/external/prompts/clinical_analysis.md tests/producers/test_clinical_analysis_producer.py
git commit -m "feat(producers): clinical_analysis — Notion fetch/analyze/write via Composio"
```

---

## Task 15: `diagnostic` producer

**Files:**
- Create: `noctua/producers/external/diagnostic.py`
- Create: `noctua/producers/external/rubrics/diagnostic.md`
- Create: `noctua/producers/external/prompts/diagnostic.md`
- Create: `tests/producers/test_diagnostic_producer.py`

- [ ] **Step 1: Write the test**

Create `tests/producers/test_diagnostic_producer.py`:

```python
import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_diagnostic_manifest():
    from noctua.producers.external.diagnostic import DiagnosticProducer
    p = DiagnosticProducer()
    assert p.key == "diagnostic"
    assert p.kind == "diagnostic"
    assert p.required_toolkits == ["LINEAR"]
    assert p.optional_toolkits == ["SLACK"]
    assert "LINEAR_GET_ISSUE" in p.composio_actions["LINEAR"]
    assert "LINEAR_CREATE_COMMENT" in p.composio_actions["LINEAR"]


def test_diagnostic_finalize_includes_comment_link():
    from noctua.producers.external.diagnostic import DiagnosticProducer
    Producer.objects.create(key="diagnostic", kind="diagnostic", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="diagnose issue ABC-123", producer_key="diagnostic", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:LINEAR.LINEAR_GET_ISSUE", "args": {"issue_id": "ABC-123"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"title": "Brakes squeal"}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "diagnose"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "Possible pad wear...", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:LINEAR.LINEAR_CREATE_COMMENT", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"comment_url": "https://linear.app/c/1"}, "error": ""}},
    ], rendered_md="")

    p = DiagnosticProducer()
    a = p.finalize(m, sandbox=None)
    assert a.preview["comment_url"] == "https://linear.app/c/1"
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/producers/test_diagnostic_producer.py -v
```

- [ ] **Step 3: Write the producer**

Create `noctua/producers/external/diagnostic.py`:

```python
from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class DiagnosticProducer(ExternalToolsProducer):
    key = "diagnostic"
    kind = "diagnostic"
    required_toolkits = ["LINEAR"]
    optional_toolkits = ["SLACK"]
    composio_actions = {
        "LINEAR": ["LINEAR_GET_ISSUE", "LINEAR_CREATE_COMMENT"],
        "SLACK":  ["SLACK_POST_MESSAGE"],
    }
    edit_prompt_file = "diagnostic.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        comment_url = ""
        slack_ts = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if not v:
                continue
            if "comment_url" in v:
                comment_url = v["comment_url"]
            if "ts" in v:
                slack_ts = v["ts"]
        return {
            "goal": mission.goal,
            "comment_url": comment_url,
            "slack_ts": slack_ts,
            "steps": steps,
        }
```

- [ ] **Step 4: Write the rubric and prompt**

Create `noctua/producers/external/rubrics/diagnostic.md`:

```
You produce a diagnostic kit for a mechanic-reported issue tracked in Linear.

Inputs:
- `goal` (required): natural-language directive containing the Linear issue ID
  (e.g. "ABC-123") or URL.
- `inputs.slack_channel` (optional): if present and SLACK is connected, also
  post the diagnostic kit summary to this channel.

Plan shape:
1. `composio:LINEAR.LINEAR_GET_ISSUE` to fetch the issue body and comments.
2. `kind: "edit"` step asking Claude to produce a diagnostic kit (likely causes,
   inspection checklist, parts to order). The edit step's result.value is the
   kit markdown.
3. `composio:LINEAR.LINEAR_CREATE_COMMENT` posting the kit back to the issue.
4. Optionally `composio:SLACK.SLACK_POST_MESSAGE` to the configured channel.
```

Create `noctua/producers/external/prompts/diagnostic.md`:

```
You are a senior automotive technician producing a diagnostic kit for a mechanic.

From the issue content in "Prior step results", produce markdown:

## Likely causes (ranked)
1. <cause> — <one-line rationale>

## Inspection checklist
- [ ] <step>

## Parts to order if confirmed
- <part> (estimated cost)

## Time estimate
<X hours>

Be specific. If the issue lacks data needed for a section, write "Need more info:
<what to ask>" instead of guessing.
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/producers/test_diagnostic_producer.py -v
```
Then:
```bash
git add noctua/producers/external/diagnostic.py noctua/producers/external/rubrics/diagnostic.md noctua/producers/external/prompts/diagnostic.md tests/producers/test_diagnostic_producer.py
git commit -m "feat(producers): diagnostic — Linear-driven diagnostic kit via Composio"
```

---

## Task 16: `cad` producer

**Files:**
- Create: `noctua/producers/external/cad.py`
- Create: `noctua/producers/external/rubrics/cad.md`
- Create: `noctua/producers/external/prompts/cad.md`
- Create: `tests/producers/test_cad_producer.py`

- [ ] **Step 1: Write the test**

Create `tests/producers/test_cad_producer.py`:

```python
import pytest
from noctua.core.models import Mission, Producer, Plan

pytestmark = pytest.mark.django_db


def test_cad_manifest():
    from noctua.producers.external.cad import CADProducer
    p = CADProducer()
    assert p.key == "cad"
    assert p.kind == "cad"
    assert p.required_toolkits == ["GOOGLEDRIVE"]
    assert p.optional_toolkits == ["NOTION"]
    assert "GOOGLEDRIVE_DOWNLOAD_FILE" in p.composio_actions["GOOGLEDRIVE"]
    assert "GOOGLEDRIVE_UPLOAD_FILE" in p.composio_actions["GOOGLEDRIVE"]


def test_cad_finalize_includes_uploaded_file_url():
    from noctua.producers.external.cad import CADProducer
    Producer.objects.create(key="cad", kind="cad", rubric_md="r", default_budget={})
    m = Mission.objects.create(goal="bracket spec", producer_key="cad", budget={"max_tool_calls": 5, "max_tokens": 10_000, "max_wall_seconds": 60})
    Plan.objects.create(mission=m, version=1, steps=[
        {"step_id": "s1", "kind": "tool",
         "payload": {"name": "composio:GOOGLEDRIVE.GOOGLEDRIVE_DOWNLOAD_FILE", "args": {"file_id": "ref1"}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"content": "ref dims..."}, "error": ""}},
        {"step_id": "s2", "kind": "edit", "payload": {"goal": "generate svg"},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": "<svg>...</svg>", "error": ""}},
        {"step_id": "s3", "kind": "tool",
         "payload": {"name": "composio:GOOGLEDRIVE.GOOGLEDRIVE_UPLOAD_FILE", "args": {}},
         "status": "succeeded", "attempt": 1,
         "result": {"ok": True, "value": {"file_url": "https://drive.google.com/file/d/abc"}, "error": ""}},
    ], rendered_md="")

    p = CADProducer()
    a = p.finalize(m, sandbox=None)
    assert a.preview["file_url"] == "https://drive.google.com/file/d/abc"
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/producers/test_cad_producer.py -v
```

- [ ] **Step 3: Write the producer**

Create `noctua/producers/external/cad.py`:

```python
from noctua.producers.external.base import ExternalToolsProducer
from noctua.core.models import Mission


class CADProducer(ExternalToolsProducer):
    key = "cad"
    kind = "cad"
    required_toolkits = ["GOOGLEDRIVE"]
    optional_toolkits = ["NOTION"]
    composio_actions = {
        "GOOGLEDRIVE": ["GOOGLEDRIVE_DOWNLOAD_FILE", "GOOGLEDRIVE_UPLOAD_FILE"],
        "NOTION":      ["NOTION_APPEND_BLOCK"],
    }
    edit_prompt_file = "cad.md"

    def _artifact_preview(self, mission: Mission, steps: list[dict]) -> dict:
        file_url = ""
        for s in steps:
            v = s.get("result") if isinstance(s.get("result"), dict) else None
            if v and "file_url" in v:
                file_url = v["file_url"]
        return {
            "goal": mission.goal,
            "file_url": file_url,
            "steps": steps,
        }
```

- [ ] **Step 4: Write rubric and prompt**

Create `noctua/producers/external/rubrics/cad.md`:

```
You generate a 2D SVG technical drawing from a reference document stored in
Google Drive.

Inputs:
- `goal` (required): natural-language directive (e.g. "draw a side view of a
  steel L-bracket sized from the spec in this PDF").
- `inputs.reference_file_id` (required): Google Drive file ID of the reference.
- `inputs.notion_page_id` (optional): if present and NOTION is connected, also
  append a link to the uploaded SVG to this Notion page.

Plan shape:
1. `composio:GOOGLEDRIVE.GOOGLEDRIVE_DOWNLOAD_FILE` to fetch the reference.
2. `kind: "edit"` step asking Claude to produce a self-contained SVG that
   encodes the requested view with the reference dimensions. The edit step's
   result.value is the SVG markup.
3. `composio:GOOGLEDRIVE.GOOGLEDRIVE_UPLOAD_FILE` to upload the SVG.
4. Optionally `composio:NOTION.NOTION_APPEND_BLOCK` to link the SVG from a page.
```

Create `noctua/producers/external/prompts/cad.md`:

```
You produce technical 2D SVG drawings.

From the reference content in "Prior step results", produce a single
self-contained SVG document (no external resources) that depicts the requested
view at 1:1 mm scale (1 user unit = 1 mm). Include:
- a 10mm scale bar at bottom-left
- linear dimensions on all critical edges (use SVG <text> with stroke-width 0)
- the title block in the bottom-right with the part name and date

Output ONLY the SVG markup (starting with <svg ...> and ending with </svg>).
No prose, no fences.
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/producers/test_cad_producer.py -v
```
Then:
```bash
git add noctua/producers/external/cad.py noctua/producers/external/rubrics/cad.md noctua/producers/external/prompts/cad.md tests/producers/test_cad_producer.py
git commit -m "feat(producers): cad — Drive-backed SVG generation via Composio"
```

---

## Task 17: Repoint entry points + `seed_producers` + delete `stub/`

**Files:**
- Modify: `pyproject.toml`
- Modify: `noctua/core/management/commands/seed_producers.py`
- Delete: `noctua/producers/stub/` (directory)

- [ ] **Step 1: Repoint entry points**

In `pyproject.toml`, replace the `[project.entry-points."noctua.producers"]` block with:

```toml
[project.entry-points."noctua.producers"]
pr = "noctua.producers.pr:PRProducer"
social_post = "noctua.producers.external.social_post:SocialPostProducer"
clinical_analysis = "noctua.producers.external.clinical_analysis:ClinicalAnalysisProducer"
diagnostic = "noctua.producers.external.diagnostic:DiagnosticProducer"
cad = "noctua.producers.external.cad:CADProducer"
```

(Drop the `tool_demo` entry — it pointed at `ToolStub` which is being deleted; verify no callers reference `tool_demo` first: `grep -r tool_demo noctua/ tests/ ui/`. If anything references it, leave a minimal placeholder producer in `noctua/producers/external/__init__.py`.)

- [ ] **Step 2: Re-install so the entry points refresh**

```bash
pip install -e ".[dev]"
```
Expected: succeeds. Re-installing is required because entry points are baked into the .egg-info at install time.

- [ ] **Step 3: Update `seed_producers`**

Open `noctua/core/management/commands/seed_producers.py`. Replace the `SEED` list:

```python
SEED = [
    ("pr", "pr", "noctua/producers/pr/rubric.md"),
    ("social_post", "social_post", "noctua/producers/external/rubrics/social_post.md"),
    ("clinical_analysis", "analysis", "noctua/producers/external/rubrics/clinical_analysis.md"),
    ("diagnostic", "diagnostic", "noctua/producers/external/rubrics/diagnostic.md"),
    ("cad", "cad", "noctua/producers/external/rubrics/cad.md"),
]
```

(`tool_demo` removed — same reason as Step 1.)

- [ ] **Step 4: Re-seed**

```bash
./manage.py seed_producers
```
Expected: five lines, each "updated producer <key>".

- [ ] **Step 5: Delete the old stub module**

```bash
git rm -r noctua/producers/stub
```
Expected: removes all five stub files plus the prompts dir.

- [ ] **Step 6: Clear the producer cache and verify imports**

```bash
python -c "from importlib.metadata import entry_points; [print(ep.load()) for ep in entry_points(group='noctua.producers')]"
```
Expected: prints each new producer class, no ImportError.

- [ ] **Step 7: Run the full test suite**

```bash
make test
```
Expected: everything passes (modulo the pre-existing flaky `tests/core/test_mission_api.py::test_create_mission` noted in CLAUDE.md).

If anything that imported from `noctua.producers.stub` breaks, fix imports to point at `noctua.producers.external`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml noctua/core/management/commands/seed_producers.py
git commit -m "feat(producers): repoint entry points to external/; remove stub/"
```

---

## Task 18: CLI: `noctua composio connect / list / disconnect`

**Files:**
- Modify: `noctua/cli.py`
- Create: `tests/test_composio_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_composio_cli.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from noctua.cli import cli

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("NOCTUA_API_URL", "http://api.test")
    monkeypatch.setenv("NOCTUA_API_TOKEN", "test-token")


def test_composio_list_calls_api(env):
    with patch("noctua.cli.httpx") as httpx:
        httpx.get.return_value = MagicMock(status_code=200, json=lambda: [
            {"toolkit": "LINKEDIN", "status": "active", "composio_conn_id": "c1",
             "connected_at": "2026-05-29T00:00:00+00:00", "last_error": ""},
        ])
        httpx.get.return_value.raise_for_status = MagicMock()
        result = CliRunner().invoke(cli, ["composio", "list"])
    assert result.exit_code == 0
    assert "LINKEDIN" in result.output
    assert "active" in result.output


def test_composio_connect_prints_url_and_polls(env):
    with patch("noctua.cli.httpx") as httpx, patch("noctua.cli.time.sleep"):
        # Initiate
        httpx.post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"toolkit": "LINKEDIN", "redirect_url": "https://o.example/x",
                          "composio_conn_id": "c1", "status": "pending"},
        )
        httpx.post.return_value.raise_for_status = MagicMock()
        # Refresh polls (3 calls: pending, pending, active)
        responses = [
            MagicMock(status_code=200, json=lambda: {"toolkit": "LINKEDIN", "status": "pending",
                      "composio_conn_id": "c1", "connected_at": None, "last_error": ""}),
            MagicMock(status_code=200, json=lambda: {"toolkit": "LINKEDIN", "status": "active",
                      "composio_conn_id": "c1", "connected_at": "2026-05-29T00:00:00+00:00",
                      "last_error": ""}),
        ]
        for r in responses:
            r.raise_for_status = MagicMock()
        httpx.post.return_value = MagicMock(status_code=201,
            json=lambda: {"toolkit": "LINKEDIN", "redirect_url": "https://o.example/x",
                          "composio_conn_id": "c1", "status": "pending"})
        httpx.post.return_value.raise_for_status = MagicMock()
        # Use side_effect for refresh calls
        # Two POSTs total: initiate + first refresh. We model both via httpx.post.side_effect.
        httpx.post.side_effect = [
            MagicMock(status_code=201,
                json=lambda: {"toolkit": "LINKEDIN", "redirect_url": "https://o.example/x",
                              "composio_conn_id": "c1", "status": "pending"},
                raise_for_status=MagicMock()),
            responses[0],
            responses[1],
        ]
        result = CliRunner().invoke(cli, ["composio", "connect", "LINKEDIN", "--timeout-seconds", "5"])
    assert result.exit_code == 0
    assert "https://o.example/x" in result.output
    assert "active" in result.output.lower()


def test_composio_disconnect_calls_api(env):
    with patch("noctua.cli.httpx") as httpx:
        httpx.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"toolkit": "LINKEDIN", "status": "revoked",
                          "composio_conn_id": "c1", "connected_at": None, "last_error": ""},
        )
        httpx.post.return_value.raise_for_status = MagicMock()
        result = CliRunner().invoke(cli, ["composio", "disconnect", "LINKEDIN"])
    assert result.exit_code == 0
    assert "revoked" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_composio_cli.py -v
```
Expected: `cli has no command 'composio'`.

- [ ] **Step 3: Add the command group**

In `noctua/cli.py`, add at the top (with the other imports):

```python
import time
```

And at the bottom, append:

```python
@cli.group()
def composio():
    """Manage Composio toolkit connections."""


def _api_url() -> str:
    return os.environ.get("NOCTUA_API_URL", "http://localhost:8000").rstrip("/")


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('NOCTUA_API_TOKEN', '')}"}


@composio.command("list")
def composio_list():
    """List all connections and their statuses."""
    r = httpx.get(f"{_api_url()}/api/connections", headers=_headers(), timeout=10)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        click.echo("(no connections)")
        return
    for c in rows:
        click.echo(f"{c['toolkit']:<20} {c['status']:<10} {c.get('connected_at') or '—'}")


@composio.command("connect")
@click.argument("toolkit")
@click.option("--timeout-seconds", default=300, show_default=True,
              help="How long to poll for OAuth completion.")
@click.option("--poll-interval-seconds", default=2, show_default=True)
def composio_connect(toolkit, timeout_seconds, poll_interval_seconds):
    """Initiate OAuth for a toolkit; open the URL in your browser."""
    toolkit = toolkit.upper()
    r = httpx.post(f"{_api_url()}/api/connections/{toolkit}/initiate",
                   headers=_headers(), timeout=15)
    r.raise_for_status()
    body = r.json()
    click.echo(f"Open this URL to authorize {toolkit}:")
    click.echo(f"  {body['redirect_url']}")
    click.echo(f"Polling for completion (up to {timeout_seconds}s)...")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(poll_interval_seconds)
        rr = httpx.post(f"{_api_url()}/api/connections/{toolkit}/refresh",
                        headers=_headers(), timeout=10)
        rr.raise_for_status()
        status = rr.json()["status"]
        if status == "active":
            click.echo(f"Connected. Status: active.")
            return
        if status in ("revoked", "expired"):
            raise click.ClickException(f"Connection ended in status {status!r}.")
    raise click.ClickException(
        f"Timed out after {timeout_seconds}s. Re-run `noctua composio list` later "
        f"or `noctua composio connect {toolkit}` to retry."
    )


@composio.command("disconnect")
@click.argument("toolkit")
def composio_disconnect(toolkit):
    """Mark a toolkit's connection as revoked (locally — does not call Composio)."""
    toolkit = toolkit.upper()
    r = httpx.post(f"{_api_url()}/api/connections/{toolkit}/disconnect",
                   headers=_headers(), timeout=10)
    r.raise_for_status()
    click.echo(f"{toolkit}: {r.json()['status']}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_composio_cli.py -v
```
Expected: 3 tests pass. (The `connect` test's mock setup is fiddly; if it fails, simplify by using `httpx.post.side_effect` consistently — the test as written above already does this.)

- [ ] **Step 5: Smoke run against a live API**

(Manual — only meaningful if you have a live API + Composio key. Skip if not.)
```bash
COMPOSIO_API_KEY=... make api &
NOCTUA_API_TOKEN=... noctua composio list
```
Expected: prints `(no connections)`.

- [ ] **Step 6: Commit**

```bash
git add noctua/cli.py tests/test_composio_cli.py
git commit -m "feat(cli): noctua composio list/connect/disconnect"
```

---

## Task 19: Final integration verification

**Files:** (no edits; verification only)

- [ ] **Step 1: Run the full test suite**

```bash
make test
```
Expected: all pass except the documented flake (`tests/core/test_mission_api.py::test_create_mission`).

- [ ] **Step 2: Smoke-run a mission end-to-end** (manual, only if you have a Composio key + at least one connected toolkit)

```bash
make up && make migrate && make seed
COMPOSIO_API_KEY=sk_test_... make api &
COMPOSIO_API_KEY=sk_test_... make worker &
# In a browser, navigate to http://localhost:3000/connections, connect LINKEDIN.
# Then:
noctua run --producer social_post --goal "Quick test post from Noctua"
```
Expected: mission queues, runs, posts to LinkedIn, lands as an Artifact in `/queue` with `posted_urls` populated.

- [ ] **Step 3: Verify pre-flight rejects unconnected missions**

```bash
noctua run --producer cad --goal "test"
```
Expected (assuming GOOGLEDRIVE is not connected): exits non-zero with the API's 400 error message mentioning `GOOGLEDRIVE`.

- [ ] **Step 4: Verify the PR producer is unaffected**

```bash
noctua run --repo https://github.com/<your>/<test-repo> --issue https://github.com/<your>/<test-repo>/issues/1 --goal "Add /healthz endpoint"
```
Expected: same behavior as before this work — sandbox boots, plan runs, PR is opened.

- [ ] **Step 5: Confirm no leftover stub references**

```bash
grep -rn "producers/stub\|producers.stub\|SocialPostStub\|ClinicalAnalysisStub\|DiagnosticStub\|CADStub\|ToolStub" . --include="*.py" --include="*.toml" 2>/dev/null
```
Expected: no matches in `noctua/` or `tests/`. (Matches under `.next/`, `.venv/`, or in committed log archives under `archive/` are OK.)

- [ ] **Step 6: No new commit needed — verification only.**

---

## Self-Review (run before handing off)

**Spec coverage check:** every section in the spec maps to one or more tasks above:
- §2 Architecture → Tasks 2, 3, 7
- §3 ComposioClient + Adapter → Tasks 2, 3
- §4 Connection model → Task 4
- §5 Producer manifest → Task 10 (base class), Tasks 13–16 (per producer)
- §6 Registry change → Task 7
- §7 external_tools lane → Tasks 8 (executor), 9 (lane), 11 (preflight), 12 (UI endpoint)
- §8 Preflight check → Task 11
- §9 CLI → Task 18
- §10 Connections UI → Task 6, 12
- §11 Per-producer specs → Tasks 13, 14, 15, 16
- §12 Settings + deps → Task 1
- §13 Budget → no change (verified in Task 9 lane test)
- §14 Error handling matrix → exercised in Tasks 3 (adapter test for auth_expired), 8 (executor sandbox=None), 9 (lane archives on failure), 11 (preflight)
- §15 Tests → present in every task
- §16 Rollout order → mirrored 1:1
- §17 Limitations → none of these change behavior; nothing to implement

**Type / name consistency:** `ToolEntry` fields used the same way everywhere (name, signature, status, callable, source_path). `ToolResult` (ok, value, error) used consistently. `ComposioClient.execute(slug=, arguments=, user_id=)` signature matches between Tasks 2 and 3. `Connection` field names (toolkit, status, composio_conn_id, connected_at, last_error) match across Tasks 4, 5, and 18. Producer attribute names (`external_tools`, `content_only`, `required_toolkits`, `optional_toolkits`, `composio_actions`, `edit_prompt_file`, `key`, `kind`) match between Task 10 and Tasks 13–16. Adapter method names (`lookup`, `list_actions_for_producer`) match between Tasks 3 and 7.

**No placeholders:** all code blocks contain real code; no TBDs.
