"""Sandbox: run bash commands in the working directory with a timeout and an output cap.

Local mode is a *soft* sandbox: it pins the working directory, strips secrets from the
environment and kills runaway commands, but a command can still touch the rest of your
machine. Docker mode (--docker IMAGE) is the real boundary: only the working directory is
mounted, and the network is off.
"""
from __future__ import annotations

import os
import signal
import subprocess

SECRET_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN")


def cap_output(text: str, limit: int) -> str:
    """Part 4: If text is longer than `limit` characters, keep the first and last limit//2
    characters and put '\\n[... N characters truncated ...]\\n' in between (N = chars removed)."""
    if len(text) <= limit:
        return text
    half = limit // 2
    cut = len(text) - 2 * half
    return text[:half] + f"\n[... {cut} characters truncated ...]\n" + text[len(text) - half:]


class Sandbox:
    def __init__(self, workdir: str, timeout: float = 60, max_output: int = 20_000, docker_image: str | None = None):
        self.workdir = os.path.realpath(workdir)
        self.timeout = timeout
        self.max_output = max_output
        self.docker_image = docker_image

    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def docker_argv(self, command: str) -> list[str]:
        """Part 4: The argv that runs `command` in a throwaway container:
        docker run --rm --network none -v <workdir>:/work -w /work <image> bash -c <command>"""
        return ["docker", "run", "--rm", "--network", "none", "-v", f"{self.workdir}:/work", "-w", "/work",
                self.docker_image, "bash", "-c", command]

    def run(self, command: str) -> str:
        """Part 4: Run `command` with bash in self.workdir (or in Docker if docker_image is set).

        Return combined stdout+stderr, capped with cap_output, followed by '\\n[exit code N]'.
        On timeout, kill the whole process group and return
        '...output so far...\\n[timed out after {timeout}s]'. Pass env=self.env().
        """
        argv = self.docker_argv(command) if self.docker_image else ["bash", "-c", command]
        proc = subprocess.Popen(argv, cwd=self.workdir, env=self.env(), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            out, _ = proc.communicate(timeout=self.timeout)
            tail = f"[exit code {proc.returncode}]"
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # the shell and everything it started
            except ProcessLookupError:
                pass
            out, _ = proc.communicate()
            tail = f"[timed out after {self.timeout}s]"
        text = cap_output(out.decode(errors="replace"), self.max_output)
        return f"{text.rstrip()}\n{tail}".lstrip()
