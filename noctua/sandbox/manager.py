import io
import os
import re
import tarfile
import docker
from dataclasses import dataclass, field


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
    def __init__(self, ttl_seconds: int = 1800):
        self.client = docker.from_env()
        self.container = None
        self.ttl_seconds = ttl_seconds
        self.info = SandboxRunInfo()

    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
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


class NestedSandbox(Sandbox):
    def boot(self, image: str, repo_url: str | None) -> SandboxRunInfo:
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
        return self.info
