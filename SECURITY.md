# Security model and isolation assumptions

PyStep executes code typed by users. This document explains what protects the server, what does not, and what a deployment needs to add.

## What is implemented

**1. The server never executes user code itself.** The FastAPI process only *parses* the submission (`ast.parse` plus a node whitelist). Execution happens in a new child process for every run (`backend/app/sandbox.py`). Tests check this.

**2. The child process starts as `python -I -S -B tracer/runner.py`, with:**

- **A minimal environment:** `PATH`, `LANG`, `LC_ALL`, `PYTHONHASHSEED`, `PYTHONIOENCODING` only. Server secrets and credentials in the parent's environment are not inherited. `os.environ` is also cleared before user code runs.
- **Isolated mode:** no user site-packages, no `PYTHON*` variables, and the current directory is not on the import path.
- **A fresh, empty temporary working directory**, deleted after the run.
- **Its own session/process group** (`start_new_session=True`). After every run, including on timeout, the parent sends `SIGKILL` to the whole group, so no stray processes are left behind.
- **Self-applied rlimits before any user code runs:** `RLIMIT_CPU` (CPU seconds), `RLIMIT_AS`/`RLIMIT_DATA` (memory; `RLIMIT_AS` is not enforced on macOS), `RLIMIT_FSIZE=0` (cannot write files), `RLIMIT_NOFILE=16`, `RLIMIT_NPROC=0` (cannot fork), `RLIMIT_CORE=0`. The list of limits that were actually applied is returned in `stats.isolation`.
- **A drop to an unprivileged uid** (`SANDBOX_UID`, default 65534), if the process was started as root.

**3. Timeouts at two levels.** The child arms a wall-clock timer and stops itself with a partial trace. If it is stuck inside a single long C call, the parent kills it 1.5 s later.

**4. Limits on what a run can produce:** maximum steps, output characters, call depth, heap objects per snapshot, items per collection and total JSON bytes.

**5. Input validation:** a code length limit (20,000 characters or 500 lines) and a JSON schema (Pydantic, `extra="forbid"`). Code that does not parse, or that uses unsupported features, is rejected before any process is started.

**6. Restricted language surface (defence in depth, *not* the security boundary):**

- Imports are limited to `math`, `random` and `string`.
- `open`, `eval`, `exec`, `compile`, `__import__`, `getattr`, `setattr`, `globals`, `vars`, `input`, etc. are removed from the builtins and rejected by the validator.
- Dunder attribute access (`x.__class__`, `f.__globals__`, …) is rejected.

**7. Safe error reporting:** the child's stderr is logged on the server and never returned to the client. Clients receive fixed, generic messages for crashes.

**8. Concurrency cap:** at most `CV_MAX_CONCURRENT_RUNS` children run at once.

## What is *not* guaranteed

A child process with rlimits is **not a sandbox**. It shares the host kernel, and its network access is the same as the server's:

- **Network:** nothing at the OS level blocks sockets. The only things standing in the way are the import whitelist and the blocked `__import__`. Python-level restrictions like these have been bypassed many times.
- **Filesystem reads:** the child can read whatever the server's user can read. `RLIMIT_FSIZE=0` prevents writing to files, but nothing prevents reading.
- **Kernel attack surface:** there is no seccomp filter, no namespace isolation and no syscall restriction.
- **Memory on macOS:** `RLIMIT_AS` is ignored there.
- **Fork limit:** `RLIMIT_NPROC` is counted per user and is ignored for root. Run the service as a dedicated user.

## Requirements for a public deployment

Treat every submission as hostile, and add OS-level isolation around the runner:

1. **Run in a container or VM** with:
   - no network: `--network none` for the runner, or a separate runner service on an internal-only network
   - a read-only root filesystem with a small `tmpfs` for `/tmp`
   - `--cap-drop ALL` and `--security-opt no-new-privileges`
   - a non-root user (the provided `Dockerfile` uses uid 10001)
   - `--pids-limit`, `--memory`, `--cpus`
2. **Add a syscall-level sandbox for the runner:** gVisor (`--runtime=runsc`), nsjail, firejail or bubblewrap, with seccomp. A straightforward hardening step is to wrap the command in `app/sandbox.py` (`[sys.executable, "-I", "-S", "-B", RUNNER]`) with `nsjail`/`bwrap` arguments.
3. **Keep secrets out of the image and out of the runner's filesystem view.** The runner gets a minimal environment, but it can still read any file it has permission to read.
4. **Put the API behind a reverse proxy** with rate limiting and request-size limits, and set `CV_CORS_ORIGINS` to your real origin.
5. **Monitor and alert** on runner crashes, timeouts and 429 responses.

## Reporting

If you find a way to escape the restrictions described above, please report it privately to the maintainers instead of opening a public issue.
