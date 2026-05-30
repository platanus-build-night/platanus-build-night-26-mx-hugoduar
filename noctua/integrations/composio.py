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
from composio import exceptions as _composio_exc  # type: ignore[import-untyped]


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


# Typed SDK exceptions that indicate an auth/credential failure.
# ApiKeyError       — API key missing or invalid
# DescopeAuthError  — Descope-backed auth failure
# ConnectedAccountError and subclasses — expired/revoked/inaccessible OAuth
#     connections (ConnectedAccountNotFoundError, InvalidConnectedAccount,
#     ComposioSharedAccessDeniedError, ComposioSharedConnectionNotAccessibleError)
# HTTPError with status 401/403 — raw HTTP auth rejection from the Composio API
_AUTH_EXCEPTIONS = (
    _composio_exc.ApiKeyError,
    _composio_exc.DescopeAuthError,
    _composio_exc.ConnectedAccountError,  # covers all subclasses
)


def _is_auth_error(exc: Exception) -> bool:
    """Return True iff exc is a composio SDK auth/credential failure."""
    if isinstance(exc, _AUTH_EXCEPTIONS):
        return True
    if isinstance(exc, _composio_exc.HTTPError) and exc.status_code in (401, 403):
        return True
    return False


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
            if _is_auth_error(e):
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


# ---- Adapter ---------------------------------------------------------------


class ComposioToolAdapter:
    """Synthesizes ToolEntry instances for composio:<TOOLKIT>.<ACTION> names.

    Usage:
        adapter = ComposioToolAdapter()  # constructs its own ComposioClient
        entry = adapter.lookup("composio:LINKEDIN.LINKEDIN_CREATE_POST")
        result = entry.callable({"text": "hi"}, sandbox=None)
    """

    def __init__(self, client: ComposioClient | None = None):
        self._client = client or get_client()
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
                # Mission pre-flight (POST /api/missions, Task 11) refuses
                # missions without an active Connection row, so a row should
                # always exist here; the .update() is a no-op only if it was
                # deleted out-of-band, which we let pass silently.
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


# ---- Singleton factory ------------------------------------------------------

_client_singleton: ComposioClient | None = None


def get_client() -> ComposioClient:
    """Return the process-wide ComposioClient (constructed lazily).

    Use this rather than `ComposioClient()` so the spec cache and SDK
    instance are shared across all callers in the process.
    """
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = ComposioClient()
    return _client_singleton


def _reset_client_for_tests() -> None:
    """Test-only hook to clear the singleton between tests that mock the SDK."""
    global _client_singleton
    _client_singleton = None
