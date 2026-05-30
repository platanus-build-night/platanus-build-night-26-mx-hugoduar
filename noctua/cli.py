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
