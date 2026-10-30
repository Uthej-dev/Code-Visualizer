"""Execution boundary between the web server and user code.

User code is **never** executed in the server process. Each run happens in a
fresh child Python process (``tracer/runner.py``) that:

* is started with ``-I -S -B`` (isolated mode: no user site-packages, no
  PYTHON* environment variables, no current-directory imports);
* receives a minimal environment (no server secrets or credentials);
* runs in an empty temporary directory that is deleted afterwards;
* lives in its own process group / session so the whole group can be killed;
* lowers its own rlimits (CPU, memory, file size, open files, processes)
  before running user code;
* is killed if it exceeds the wall-clock timeout.

This is process-level isolation, **not** a complete sandbox. A subprocess
shares the kernel, the network stack and (read-only) filesystem visibility
with the server. For a public deployment run the server (or at least the
runner) inside a container/VM with no network, a read-only root filesystem,
an unprivileged user and seccomp/gVisor — see SECURITY.md.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from tracer.engine import TraceLimits, error_result
from tracer.validator import ValidationError, validate_source

from .config import Settings, settings as default_settings

log = logging.getLogger("codeviz.sandbox")

RUNNER = Path(__file__).resolve().parent.parent / "tracer" / "runner.py"
MINIMAL_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONIOENCODING": "utf-8"}


def _limit_error(message: str, limits: TraceLimits) -> dict:
    return error_result(
        {"phase": "limit", "type": "LimitExceeded", "message": message, "line": None, "column": None},
        limits,
    )


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:  # pragma: no cover - Windows
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_code(code: str, config: Settings = default_settings) -> dict:
    limits = TraceLimits(
        max_steps=config.max_steps,
        max_output_chars=config.max_output_chars,
        max_trace_bytes=config.max_trace_bytes,
    )
    # Fast, in-process *static* validation (parsing only, no execution).
    try:
        validate_source(code)
    except ValidationError as err:
        return error_result(err, limits)

    payload = json.dumps({
        "code": code,
        "limits": asdict(limits),
        "cpu_seconds": config.cpu_seconds,
        "memory_mb": config.memory_mb,
        "wall_seconds": config.wall_timeout_seconds,
    }).encode()

    with tempfile.TemporaryDirectory(prefix="codeviz-run-") as workdir:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", str(RUNNER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
            env=MINIMAL_ENV,
            close_fds=True,
            start_new_session=True,
        )
        try:
            # The child stops itself at wall_seconds; the extra second covers
            # code stuck inside a single long C call (e.g. 10**10**8).
            stdout, stderr = proc.communicate(payload, timeout=config.wall_timeout_seconds + 1.5)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.communicate()
            return _limit_error(
                f"The program did not finish within {config.wall_timeout_seconds:g} seconds and was stopped. "
                "It may contain an infinite loop or a very slow computation.",
                limits,
            )
        finally:
            _kill_group(proc)  # clean up anything the child left behind

    if stderr:
        log.info("runner stderr: %s", stderr[:2000].decode("utf-8", "replace"))

    if len(stdout) > limits.max_trace_bytes + 100_000:
        return _limit_error("The execution trace was too large.", limits)
    try:
        result = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        rc = proc.returncode
        if rc is not None and rc < 0:
            sig = -rc
            if sig in (getattr(signal, "SIGXCPU", -1), signal.SIGKILL):
                return _limit_error("The program used too much CPU time or memory and was stopped.", limits)
            return _limit_error(f"The program was stopped by the operating system (signal {sig}).", limits)
        if b"MemoryError" in stderr:
            return _limit_error("The program used too much memory and was stopped.", limits)
        return error_result(
            {"phase": "internal", "type": "ExecutionError", "message": "The program could not be executed. Please try again.", "line": None, "column": None},
            limits,
        )
    return result
