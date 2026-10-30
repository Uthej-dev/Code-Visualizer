# PyStep: Python code visualizer and step-by-step debugger

PyStep runs a Python program and lets you step through it one event at a time. At each step you see:

- the line that just ran, plus a marker for the line that runs next
- every variable with its value, type and scope, and whether this step created, changed (re-bound), modified (mutated) or deleted it
- lists, tuples, dicts, sets and objects drawn as boxes, with arrows from variables to the objects they refer to, so shared references are easy to spot
- the call stack, with a separate frame for each call (recursion included) and each function's return value
- the program's output up to that step
- a plain-language explanation built from the real values in the run, e.g. `Read a → 3 · Read b → 4 · Compute 3 + 4 → 7 · Create variable c and store 7 in it`

You can move with First / Previous / Next / Last, Play/Pause at four speeds, or drag the timeline. Every step is a complete snapshot, so going backwards restores the exact state. Nothing is replayed or undone.

## Quick start

Requirements: **Python 3.11+** (3.12 is the tested version) and **Node.js 18+** (22 is the tested version). Tested on macOS. Linux should work. On Windows the backend runs, but it has no rlimit isolation.

```bash
# 1. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 2. Frontend
cd ../frontend
npm install

# 3. Run both (backend on :8000, frontend on :5173)
cd ..
./dev.sh
```

Open <http://localhost:5173>. Pick a sample from the menu and press **Run & visualize** (or <kbd>Ctrl/⌘</kbd>+<kbd>Enter</kbd>).

To start the two processes separately:

```bash
cd backend  && .venv/bin/uvicorn app.main:app --port 8000   # API
cd frontend && npm run dev                                    # UI (proxies /api to :8000)
```

### Keyboard shortcuts

| Key | Action |
| --- | --- |
| <kbd>→</kbd> / <kbd>←</kbd> | Next / previous step |
| <kbd>Home</kbd> / <kbd>End</kbd> | First / last step |
| <kbd>Space</kbd> | Play / pause |
| <kbd>Ctrl/⌘</kbd>+<kbd>Enter</kbd> | Run |

The step shortcuts do nothing while the cursor is in the editor, so they don't get in the way of typing. Click outside the editor to use them.

## Tests

```bash
cd backend  && .venv/bin/python -m pytest     # 64 tests: tracer, sandbox, API, all 10 samples end-to-end
cd frontend && npm test                       # 29 tests: navigation reducer, trace helpers, full App behaviour
cd frontend && npm run typecheck              # strict TypeScript
```

The frontend tests use **real traces exported from the backend** (`frontend/src/test/fixtures/*.json`), not hand-written mocks. Regenerate them after changing the trace format:

```bash
cd backend && .venv/bin/python scripts/export_fixtures.py
```

## Architecture

```
┌────────────── Browser (React + TS + Vite + Tailwind) ─────────────┐
│ Monaco editor │ Memory diagram (HTML + SVG arrows) │ Explanation / │
│               │ Variables table · History          │ Output/Errors │
│                    Controls · timeline · speed     │ Call stack    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ POST /api/trace {code}
┌──────────────────────────────▼─────────────────────────────────────┐
│ FastAPI (backend/app)                                               │
│  • validates input (size, syntax, supported subset): no execution  │
│  • limits concurrent runs                                           │
│  • spawns one isolated child process per run  (app/sandbox.py)      │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ stdin: code + limits / stdout: trace JSON
┌──────────────────────────────▼─────────────────────────────────────┐
│ Child: python -I -S -B tracer/runner.py                             │
│  • empty temp dir, minimal env, own process group, rlimits          │
│  • tracer/engine.py: sys.settrace → one snapshot per event          │
└─────────────────────────────────────────────────────────────────────┘
```

| Path | Purpose |
| --- | --- |
| `backend/tracer/validator.py` | Parses the code and rejects syntax outside the supported subset, with line and column. |
| `backend/tracer/engine.py` | Tracing engine. Turns `sys.settrace` events into `line`/`call`/`return`/`exception`/`finish` steps. Enforces step, output and call-depth limits. |
| `backend/tracer/serialize.py` | Encodes frames and the reachable heap. Every object gets a **stable id** (`o1`, `o2`, …) that stays the same across all steps. |
| `backend/tracer/diff.py` | Compares consecutive snapshots: created / **rebound** / **mutated** / removed variables, and which list indexes or dict keys changed. |
| `backend/tracer/explain.py` | Beginner explanations. It re-evaluates only side-effect-free expressions on builtin values; everything else is described from observed changes. |
| `backend/tracer/runner.py` | Entry point of the isolated child process. |
| `backend/app/sandbox.py` | Parent side of the execution boundary: spawn, timeout, kill the process group, clean up. |
| `backend/app/models.py` ↔ `frontend/src/types/trace.ts` | The trace format, defined as Pydantic models and as TypeScript types (keep the two in sync). |
| `frontend/src/lib/navigation.ts` | Pure navigation reducer (first/prev/next/last/jump/play/tick). |
| `frontend/src/components/MemoryView.tsx`, `ArrowLayer.tsx` | Frames, objects and SVG reference arrows. The arrows are drawn from the rendered DOM. |
| `shared/samples/` | The 10 sample programs. The frontend bundles them and the backend tests run them. |

### Trace format (summary)

```jsonc
{
  "status": "ok" | "error" | "limit" | "internal",
  "output": "full program output",
  "error": { "phase": "syntax|unsupported|runtime|limit|...", "type", "message", "line", "hint" } | null,
  "steps": [{
    "index": 4, "eventId": "e5",
    "event": "line" | "call" | "return" | "exception" | "finish",
    "line": 6, "endLine": 6, "frameId": "global", "funcName": "Global frame",
    "stack": [{ "id": "global", "name": "Global frame", "line": 6,
                "locals": [{ "name": "scores", "value": { "kind": "ref", "id": "o1" } }],
                "returnValue": null }],
    "heap": { "o1": { "id": "o1", "type": "list", "items": [{ "kind": "prim", "type": "int", "repr": "70" }] } },
    "outputLength": 0,                      // output visible at this step = output[:outputLength]
    "changes": [{ "frameId": "global", "name": "scores", "kind": "mutated", "before": …, "after": … }],
    "heapChanges": [{ "id": "o1", "kind": "mutated", "changed": [], "added": ["3"], "removed": [] }],
    "summary": "Call scores.append(…)",
    "explanation": ["The list scores was modified in place: added [3] = 100. …"],
    "exception": null, "condition": null, "loop": null
  }]
}
```

**Step semantics.** A `line` step shows the state *after* that statement finished. A statement that calls a function is reported after the callee's steps, because only then has it finished. So `r = f(2)` appears as: call f → f's lines → f returns → `r = f(2)` assigns `r`. A source line that runs several times (a loop header, for example) produces a separate step, with its own `eventId`, each time.

## Supported Python

**Tested and supported:** assignment (including tuple unpacking and augmented assignment), arithmetic, comparisons, boolean logic, `if/elif/else`, `for` and `while` (with `break`, `continue`, `else`), lists, tuples, dicts, sets, strings, f-strings, functions, default arguments, `return`, nested calls, recursion, lambdas, list/dict/set comprehensions, closures with `nonlocal`/`global`, `try/except/finally`, `raise`, `assert`, `del`, simple classes with instance attributes, `print`, and imports of `math`, `random` and `string`.

**Rejected with a clear message:** other imports, `input()`, `open`/`eval`/`exec`/`getattr`/…, dunder attribute access (e.g. `__class__`), generators (`yield`), generator expressions, `async`/`await`, `with`, `match`, decorators, metaclasses.

## Known limitations

- **One statement per line.** `a = 1; b = 2` is shown as one step. A one-line compound statement such as `if x: y = 1` is shown on its header line.
- **Explanations show the operation breakdown only for pure expressions** made of builtin values (numbers, strings, lists, dicts, indexing, `len`, `min`, …). For expressions that call user functions or methods, the explanation lists what happened instead: the calls and their return values, the variables that changed, and what was printed. It never guesses.
- **List comprehensions are a single step** on Python 3.12, which inlines them. A lambda called inside a comprehension still gets its own call/return steps.
- **Object identity is kept for the whole run.** The tracer holds a reference to every object it has labelled, so ids are never reused. As a side effect, objects that become unreachable are not freed until the run ends. This has no visible effect on beginner programs.
- **Collections show their first 100 items. Each snapshot shows up to 200 objects.** Larger structures are cut off and marked as truncated.
- **Limits per run:** 1,000 steps, 20,000 output characters, 100 nested calls, about 5 s wall-clock time, 4 s CPU time. Hitting a limit stops the run, keeps the steps recorded so far, and says which limit was reached. The limits are configurable (see below).
- **Memory limit:** `RLIMIT_AS` is enforced on Linux. macOS does not enforce it, so there the CPU and wall-clock limits are what stop a runaway allocation.
- **`random` is not seeded.** Each run of a program that uses it can produce a different trace.

## Configuration

These environment variables are read by the backend:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CV_WALL_TIMEOUT` | `5` | Wall-clock seconds per run (the parent kills the process 1.5 s after this) |
| `CV_CPU_SECONDS` | `4` | `RLIMIT_CPU` for the child |
| `CV_MEMORY_MB` | `256` | `RLIMIT_AS` / `RLIMIT_DATA` for the child |
| `CV_MAX_STEPS` | `1000` | Maximum recorded steps |
| `CV_MAX_OUTPUT_CHARS` | `20000` | Maximum printed characters |
| `CV_MAX_TRACE_BYTES` | `8000000` | Maximum JSON size (trailing steps are dropped if it is larger) |
| `CV_MAX_CONCURRENT_RUNS` | `4` | Runs allowed at the same time; extra requests wait up to 10 s, then get HTTP 429 |
| `CV_CORS_ORIGINS` | `http://localhost:5173,…` | Allowed browser origins for the API |

The frontend reads `VITE_API_BASE` (default: same origin) and, in development, `VITE_API_TARGET` (the proxy target, default `http://127.0.0.1:8000`).

## Deployment

```bash
docker build -t pystep .
docker run --rm -p 8000:8000 \
  --read-only --tmpfs /tmp:size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 64 --memory 512m --cpus 1 \
  pystep
```

The image builds the frontend and serves it from FastAPI, so the UI and the API share one origin on port 8000. **Before exposing it to untrusted users, read [SECURITY.md](SECURITY.md).** The process boundary alone is not a complete sandbox.
