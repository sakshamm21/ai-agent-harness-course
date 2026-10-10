"""Part 4: sandbox. bash runs in the working dir, with a timeout, an output cap and no secrets."""
import os
import time

from nanoharness.sandbox import Sandbox, cap_output


def test_cap_output_keeps_head_and_tail():
    assert cap_output("short", 100) == "short"
    text = "a" * 50 + "b" * 50
    out = cap_output(text, 20)
    assert out.startswith("a" * 10) and out.endswith("b" * 10)
    assert "[... 80 characters truncated ...]" in out


def test_runs_in_the_working_dir_and_reports_exit_code(tmp_path):
    sb = Sandbox(str(tmp_path))
    out = sb.run("pwd && echo hi")
    assert os.path.realpath(str(tmp_path)) in out and "hi" in out
    assert out.endswith("[exit code 0]")
    assert sb.run("echo oops >&2; exit 3").endswith("oops\n[exit code 3]")
    sb.run("echo data > made.txt")
    assert (tmp_path / "made.txt").read_text() == "data\n"


def test_timeout_kills_the_command(tmp_path):
    sb = Sandbox(str(tmp_path), timeout=0.5)
    start = time.time()
    out = sb.run("echo started; sleep 10; echo never")
    assert time.time() - start < 5
    assert "started" in out and "never" not in out
    assert out.endswith("[timed out after 0.5s]")


def test_output_is_capped(tmp_path):
    out = Sandbox(str(tmp_path), max_output=1000).run("python3 -c \"print('x' * 50000)\"")
    assert len(out) < 1200 and "characters truncated" in out


def test_secrets_are_not_passed_to_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    out = Sandbox(str(tmp_path)).run("echo key=${ANTHROPIC_API_KEY:-none}")
    assert "key=none" in out


def test_docker_mode_mounts_only_the_workdir(tmp_path):
    sb = Sandbox(str(tmp_path), docker_image="python:3.12-slim")
    argv = sb.docker_argv("pytest -q")
    assert argv[:3] == ["docker", "run", "--rm"]
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
    assert f"{os.path.realpath(str(tmp_path))}:/work" in argv
    assert argv[-4:] == ["python:3.12-slim", "bash", "-c", "pytest -q"]
