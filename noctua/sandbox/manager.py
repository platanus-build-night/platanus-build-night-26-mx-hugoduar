import os
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
        if repo_url:
            # install git + gh inside the container so producer can run gh pr create later
            self.exec(
                [
                    "bash",
                    "-lc",
                    "apt-get update -qq && "
                    "apt-get install -qq -y git curl ca-certificates && "
                    "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && "
                    "chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && "
                    "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main' > /etc/apt/sources.list.d/github-cli.list && "
                    "apt-get update -qq && apt-get install -qq -y gh && "
                    "gh auth setup-git && "
                    f"git clone {repo_url} /work",
                ],
                timeout=600,
            )
        return self.info

    def exec(self, cmd: list[str], stdin: str = "", timeout: int = 60):
        # placeholder — full impl in Task 12
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
