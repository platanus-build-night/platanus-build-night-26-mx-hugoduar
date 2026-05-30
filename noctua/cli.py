import os
import time
import click
import httpx


@click.group()
def cli():
    """Noctua — overnight artifact factory."""


@cli.command()
@click.option("--repo", default="", help="GitHub repo URL (required for PR missions)")
@click.option("--issue", default="", help="GitHub issue URL (required for PR missions)")
@click.option("--goal", required=True, help="Mission goal — what should Noctua produce?")
@click.option("--producer", default="pr", show_default=True,
              type=click.Choice(["pr", "social_post", "clinical_analysis", "diagnostic", "cad"], case_sensitive=False),
              help="Which producer should run this mission.")
def run(repo, issue, goal, producer):
    """Queue a mission."""
    if producer == "pr" and not repo:
        raise click.UsageError("--repo is required for PR missions.")

    api_url = os.environ.get("NOCTUA_API_URL", "http://localhost:8000")
    token = os.environ.get("NOCTUA_API_TOKEN", "")
    payload = {
        "goal": goal,
        "producer_key": producer,
        "repo_url": repo,
        "issue_url": issue,
    }
    r = httpx.post(
        f"{api_url}/api/missions",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    click.echo(f"Mission {body['id']} queued ({producer}).")


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
            click.echo("Connected. Status: active.")
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
