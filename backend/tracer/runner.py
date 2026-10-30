"""Entry point of the isolated child process that executes user code.

Started by ``app.sandbox`` as::

    python -I -S -B tracer/runner.py

with a minimal environment, an empty temporary working directory and its own
process group. It reads ``{"code": ..., "limits": {...}, "cpu_seconds": ...,
"memory_mb": ..., "wall_seconds": ...}`` as JSON on stdin and writes exactly
one JSON trace document on stdout, then exits.

Before any user code runs it lowers its own resource limits (CPU time,
address space, file size, open files, child processes) and, when started as
root, drops to an unprivileged uid. These are best-effort OS limits; see
SECURITY.md for what they do and do not guarantee.
"""

from __future__ import annotations

import json
import os
import signal
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Modules user code may import are loaded *before* limits are applied so that
# importing them later needs no filesystem access.
import math  # noqa: E402,F401
import random  # noqa: E402,F401
import string  # noqa: E402,F401

from tracer.engine import TraceLimits, Tracer, error_result, fit_to_size  # noqa: E402
from tracer.validator import ValidationError  # noqa: E402

applied_limits: list[str] = []


def _write_and_exit(text: str, code: int = 0) -> None:
    data = text.encode("utf-8", "replace")
    view = memoryview(data)
    while view:
        try:
            written = os.write(1, view)
        except InterruptedError:
            continue
        view = view[written:]
    os._exit(code)


def apply_resource_limits(cpu_seconds: int, memory_mb: int) -> None:
    try:
        import resource
    except ImportError:  # Windows: no rlimits, rely on the parent's timeout
        return

    def setlimit(name: str, soft: int, hard: int | None = None) -> None:
        kind = getattr(resource, name, None)
        if kind is None:
            return
        hard = soft if hard is None else hard
        try:
            cur_soft, cur_hard = resource.getrlimit(kind)
            if cur_hard != resource.RLIM_INFINITY:
                hard = min(hard, cur_hard)
                soft = min(soft, hard)
            resource.setrlimit(kind, (soft, hard))
            applied_limits.append(name)
        except (ValueError, OSError):
            pass

    setlimit("RLIMIT_CPU", cpu_seconds, cpu_seconds + 1)
    if sys.platform != "darwin":  # macOS does not enforce RLIMIT_AS
        setlimit("RLIMIT_AS", memory_mb * 1024 * 1024)
    setlimit("RLIMIT_DATA", memory_mb * 1024 * 1024)
    setlimit("RLIMIT_FSIZE", 0)
    setlimit("RLIMIT_CORE", 0)
    setlimit("RLIMIT_NOFILE", 16)
    setlimit("RLIMIT_NPROC", 0)


def drop_privileges() -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        nobody = int(os.environ.get("SANDBOX_UID", "65534"))
        try:
            os.setgroups([])
            os.setgid(nobody)
            os.setuid(nobody)
            applied_limits.append("setuid")
        except OSError:
            pass


def main() -> None:
    try:
        request = json.loads(sys.stdin.read())
        code = request["code"]
        limits = TraceLimits(**request.get("limits", {}))
        cpu_seconds = int(request.get("cpu_seconds", 5))
        memory_mb = int(request.get("memory_mb", 256))
        wall_seconds = float(request.get("wall_seconds", 5))
    except Exception:
        _write_and_exit(json.dumps(error_result({
            "phase": "input", "type": "InputError", "message": "Malformed execution request.",
            "line": None, "column": None,
        })))
        return
    sys.stdin.close()
    os.environ.clear()

    def finish(tracer: Tracer) -> None:
        result = tracer.result()
        result["stats"]["isolation"] = applied_limits
        _write_and_exit(fit_to_size(result, limits.max_trace_bytes))

    try:
        tracer = Tracer(code, limits, on_abort=finish)
    except ValidationError as err:
        _write_and_exit(json.dumps(error_result(err, limits)))
        return

    def on_timeout(signum, frame):
        try:
            tracer.abort("time")
        except BaseException:
            pass
        finish(tracer)

    drop_privileges()
    apply_resource_limits(cpu_seconds, memory_mb)
    if hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, on_timeout)
        signal.setitimer(signal.ITIMER_REAL, wall_seconds)
    sys.setrecursionlimit(max(sys.getrecursionlimit(), limits.max_stack_depth * 4 + 200))

    tracer.run()
    if hasattr(signal, "setitimer"):
        signal.setitimer(signal.ITIMER_REAL, 0)
    finish(tracer)


if __name__ == "__main__":
    main()
