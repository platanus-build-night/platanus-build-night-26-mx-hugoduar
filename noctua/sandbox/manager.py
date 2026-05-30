import io
import os
import re
import tarfile
import time
import docker
from dataclasses import dataclass, field
from datetime import datetime


_REPO_URL_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+(\.git)?/?$")


def _validate_repo_url(repo_url: str) -> str:
    if not _REPO_URL_RE.match(repo_url):
        raise ValueError(f"unsafe repo_url: {repo_url!r}")
    return repo_url


@dataclass
class SandboxRunInfo:
    container_id: str = ""
    image_ref: str = ""
    state: str = "booting"
    log_path: str = ""


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class Sandbox:
    def __init__(self, ttl_seconds: int = 1800, log_path: str | None = None, *, mission_id: int | None = None):
        self.client = docker.from_env()
        self.container = None
        self.ttl_seconds = ttl_seconds
        self.log_path = log_path
        self.mission_id = mission_id
        self.sandbox_run_id: int | None = None
        self._log_file = None
        self.info = SandboxRunInfo()
        if log_path:
            self.info.log_path = log_path

    def _open_log(self):
        """Open the log file lazily for line-buffered append."""
        if self._log_file is not None or not self.log_path:
            return
        try:
            self._log_file = open(self.log_path, "a", buffering=1)
        except OSError:
            pass

    def _log(self, text: str):
        """Write a timestamped log line. Best-effort — never raises."""
        if not self.log_path:
            return
        try:
            self._open_log()
            if self._log_file:
                ts = datetime.now().strftime("%H:%M:%S")
                self._log_file.write(f"[{ts}] {text}\n")
                self._log_file.flush()
        except OSError:
            pass

    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
        self._open_log()
        self._log(f"BOOT image={image} repo={repo_url or '-'}")
        self.client.images.pull(image)  # idempotent
        env = {}
        if os.environ.get("GITHUB_TOKEN"):
            env["GITHUB_TOKEN"] = os.environ["GITHUB_TOKEN"]
        self.container = self.client.containers.run(
            image,
            command="sleep infinity",
            detach=True,
            nano_cpus=2_000_000_000,  # 2 cores (cpu_count is Windows-only in docker-py)
            mem_limit="2g",
            working_dir="/work",
            tmpfs={"/work": "rw,size=512m"},
            network_mode="bridge",
            labels={"noctua.role": "mission"},
            environment=env,
        )
        self.info.container_id = self.container.id
        self.info.image_ref = image
        self.info.state = "ready"
        self._log(f"BOOT_OK container={self.container.id}")
        if self.mission_id is not None:
            try:
                from noctua.core.models import SandboxRun
                from django.utils.timezone import now
                run = SandboxRun.objects.create(
                    mission_id=self.mission_id,
                    image_ref=image,
                    container_id=self.container.id,
                    state="ready",
                    log_path=self.log_path or "",
                    ttl_seconds=self.ttl_seconds,
                    started_at=now(),
                )
                self.sandbox_run_id = run.id
            except Exception:
                pass
        # Always bootstrap dev tools + git identity so any git command works,
        # regardless of whether the LLM uses the bundled tool or raw bash.
        # gh auth setup-git is gated on GITHUB_TOKEN presence to stay a no-op
        # when the token is absent.
        # NOTE: future optimisation — bake these into a custom image so boot is faster.
        self.exec(
            [
                "bash",
                "-lc",
                "set -e && "
                "apt-get update -qq && "
                "apt-get install -qq -y git curl ca-certificates && "
                "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg "
                "  | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && "
                "chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && "
                "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] "
                "https://cli.github.com/packages stable main' "
                "  > /etc/apt/sources.list.d/github-cli.list && "
                "apt-get update -qq && apt-get install -qq -y gh && "
                "git config --global user.email 'noctua@local' && "
                "git config --global user.name 'Noctua' && "
                "git config --global init.defaultBranch main && "
                "( [ -n \"$GITHUB_TOKEN\" ] && gh auth setup-git || true )",
            ],
            timeout=600,
        )
        # Conditionally clone if a repo_url was provided.
        if repo_url:
            _validate_repo_url(repo_url)
            self.exec(["git", "clone", "--", repo_url, "/work"], timeout=300)
        return self.info

    def exec(self, cmd: list[str], stdin: str = "", timeout: int = 60) -> ExecResult:
        cmd_str = " ".join(cmd)
        if len(cmd_str) > 500:
            cmd_str = cmd_str[:500] + "…"
        self._log(f"EXEC {cmd_str}")
        # docker SDK exec doesn't honor stdin easily; for stdin we'd shell-wrap.
        # For MVP we ignore stdin and accept timeout via daemon-side wait.
        result = self.container.exec_run(cmd, demux=True)
        stdout_b, stderr_b = result.output if isinstance(result.output, tuple) else (result.output, None)
        exec_result = ExecResult(
            exit_code=result.exit_code,
            stdout=(stdout_b or b"").decode("utf-8", "replace"),
            stderr=(stderr_b or b"").decode("utf-8", "replace"),
        )
        self._log(f"EXIT {exec_result.exit_code}")
        # Dump stdout block (clipped to 4000 chars)
        if exec_result.stdout:
            stdout_body = exec_result.stdout[:4000]
            lines = "\n".join(f" {l}" for l in stdout_body.splitlines())
            self._log(f"STDOUT:\n{lines}")
        # Dump stderr block (clipped to 4000 chars)
        if exec_result.stderr:
            stderr_body = exec_result.stderr[:4000]
            lines = "\n".join(f" {l}" for l in stderr_body.splitlines())
            self._log(f"STDERR:\n{lines}")
        return exec_result

    def write_file(self, path: str, content: bytes) -> None:
        self._log(f"WRITE_FILE {path} ({len(content)} bytes)")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=path.lstrip("/"))
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        buf.seek(0)
        self.container.put_archive("/", buf.read())

    def read_file(self, path: str) -> bytes:
        self._log(f"READ_FILE {path}")
        stream, _ = self.container.get_archive(path)
        buf = io.BytesIO()
        for chunk in stream:
            buf.write(chunk)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            member = tar.next()
            f = tar.extractfile(member)
            return f.read() if f else b""

    def teardown(self):
        self._log("TEARDOWN")
        try:
            if self._log_file:
                self._log_file.close()
                self._log_file = None
        except OSError:
            pass
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
        # Best-effort DB update; ignore failures
        if self.sandbox_run_id is not None:
            try:
                from noctua.core.models import SandboxRun
                from django.utils.timezone import now
                SandboxRun.objects.filter(id=self.sandbox_run_id).update(
                    state="torn_down", finished_at=now(),
                )
                self.sandbox_run_id = None  # don't double-update
            except Exception:
                pass


class NestedSandbox(Sandbox):
    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
        self._open_log()
        self._log(f"BOOT image={image} repo={repo_url or '-'}")
        self.client.images.pull(image)
        self.container = self.client.containers.run(
            image,
            command="sleep infinity",
            detach=True,
            nano_cpus=1_000_000_000,  # 1 core
            mem_limit="512m",
            working_dir="/work",
            tmpfs={"/work": "rw,size=128m"},
            network_mode="none",
            labels={"noctua.role": "fabrication"},
        )
        self.info.container_id = self.container.id
        self.info.image_ref = image
        self.info.state = "ready"
        self._log(f"BOOT_OK container={self.container.id}")
        return self.info
