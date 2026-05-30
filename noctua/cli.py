import os
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
