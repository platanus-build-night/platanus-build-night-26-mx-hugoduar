# noctua/tools/bundled.py
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
    r = sandbox.exec(["bash", "-lc", "cd /work && git push -u origin HEAD"])
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
