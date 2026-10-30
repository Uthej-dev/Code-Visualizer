"""Tests for the process boundary and resource limits."""

import os
import subprocess

from app import sandbox
from app.config import Settings


def test_runs_in_child_process_not_server():
    marker = "codeviz_should_not_exist"
    result = sandbox.run_code(f"{marker} = 1\n")
    assert result["status"] == "ok"
    assert marker not in globals()


def test_child_gets_minimal_environment(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "hunter2")
    captured = {}
    real_popen = subprocess.Popen

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(sandbox.subprocess, "Popen", spy)
    assert sandbox.run_code("x = 1\n")["status"] == "ok"
    assert "SECRET_TOKEN" not in captured["env"]
    assert set(captured["env"]) <= set(sandbox.MINIMAL_ENV)
    assert captured["start_new_session"] is True
    assert os.path.basename(captured["cwd"]).startswith("codeviz-run-")
    assert not os.path.exists(captured["cwd"]), "temporary working directory must be removed"


def test_infinite_loop_is_stopped():
    result = sandbox.run_code("while True:\n    pass\n")
    assert result["status"] == "limit"
    assert result["steps"], "partial trace should be returned"


def test_wall_clock_timeout_without_trace_events():
    config = Settings(wall_timeout_seconds=1.0, cpu_seconds=10)
    result = sandbox.run_code("x = 7 ** 30000000\n", config)  # one long C-level computation
    assert result["status"] == "limit"


def test_validation_happens_before_spawning(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not spawn a process for invalid code")

    monkeypatch.setattr(sandbox.subprocess, "Popen", boom)
    assert sandbox.run_code("import socket\n")["error"]["phase"] == "unsupported"
    assert sandbox.run_code("def (:\n")["error"]["phase"] == "syntax"


def test_resource_limits_reported():
    result = sandbox.run_code("x = 1\n")
    applied = result["stats"].get("isolation") or []
    if hasattr(os, "getrlimit") or os.name == "posix":
        assert "RLIMIT_CPU" in applied and "RLIMIT_FSIZE" in applied
