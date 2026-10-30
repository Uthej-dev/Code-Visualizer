"""The tracing engine: runs code under ``sys.settrace`` and records one
deterministic, self-contained snapshot per execution event.

Step semantics
--------------
* ``line``      – a statement **finished** running; the snapshot shows the
                  state right after it (this is what a beginner expects:
                  "line 3 ran, now c is 7").
* ``call``      – a function was entered; the new frame holds its arguments.
* ``return``    – a function is about to hand back its return value.
* ``exception`` – an exception was raised at this line.
* ``finish``    – the program completed normally.

A statement that calls a function is reported *after* the callee's steps,
because only then has the statement finished (e.g. ``r = f(2)`` shows the
call, f's lines, f's return, then the assignment to ``r``).

Every step carries the full stack, the full reachable heap and the length of
the output produced so far, so the frontend can jump to any step without
replaying anything.
"""

from __future__ import annotations

import ast
import builtins as _builtins
import io
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from . import explain
from .diff import diff_snapshots
from .serialize import NO_VALUE, HeapEncoder
from .statements import LOOPS, StatementIndex, block_of
from .validator import ALLOWED_IMPORTS, FORBIDDEN_NAMES, ValidationError, validate_source

USER_FILENAME = "<user_code>"
TRACE_FORMAT_VERSION = 1


@dataclass
class TraceLimits:
    max_steps: int = 1000
    max_output_chars: int = 20_000
    max_stack_depth: int = 100
    max_heap_objects: int = 200
    max_collection_items: int = 100
    max_trace_bytes: int = 8_000_000


class TraceAbort(BaseException):
    """Raised (in-process mode) to stop user code when a limit is hit."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class LimitedOutput(io.TextIOBase):
    def __init__(self, limit: int, on_limit: Callable[[], None]):
        self.limit = limit
        self.parts: list[str] = []
        self.size = 0
        self.on_limit = on_limit

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("write() argument must be str")
        room = self.limit - self.size
        if len(text) > room:
            self.parts.append(text[:room])
            self.size = self.limit
            self.on_limit()
            return len(text)
        self.parts.append(text)
        self.size += len(text)
        return len(text)

    def getvalue(self) -> str:
        return "".join(self.parts)


def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"Importing '{name}' is not allowed in the visualizer")
    return __import__(name, globals, locals, fromlist, level)


def safe_builtins() -> dict:
    allowed = {}
    for name in dir(_builtins):
        if name in FORBIDDEN_NAMES or name.startswith("_"):
            continue
        allowed[name] = getattr(_builtins, name)
    allowed["__build_class__"] = _builtins.__build_class__
    allowed["__import__"] = _restricted_import
    allowed["__name__"] = "builtins"
    return allowed


@dataclass
class Pending:
    """A statement that started running but has not finished yet."""

    stmt: ast.AST | None
    line: int
    end_line: int
    pre: explain.PreInfo
    output_len: int
    calls: list[str] = field(default_factory=list)


@dataclass
class FrameInfo:
    id: str
    name: str
    frame: Any
    is_global: bool
    pending: Pending | None = None
    last_line: int | None = None
    loop_counts: dict[int, int] = field(default_factory=dict)
    unwinding: bool = False
    is_class_body: bool = False
    call_text: str = ""
    return_value: Any = NO_VALUE


class Tracer:
    def __init__(self, source: str, limits: TraceLimits | None = None,
                 on_abort: Callable[["Tracer"], None] | None = None):
        self.source = source
        self.lines = source.splitlines()
        self.limits = limits or TraceLimits()
        self.on_abort = on_abort
        self.tree = validate_source(source)
        self.index = StatementIndex(self.tree)
        self.encoder = HeapEncoder(self.limits.max_heap_objects, self.limits.max_collection_items)
        self.output = LimitedOutput(self.limits.max_output_chars, lambda: self.abort("output"))
        self.builtins = safe_builtins()
        self.globals: dict = {}
        self.steps: list[dict] = []
        self.frames: dict[int, FrameInfo] = {}
        self.frame_counter = 0
        self.prev_stack: list[dict] = []
        self.prev_heap: dict = {}
        self.reported_exceptions: dict[int, tuple[BaseException, int]] = {}
        self.status = "ok"
        self.error: dict | None = None
        self.limit_reason: str | None = None
        self.started = time.perf_counter()
        self.finished = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> dict:
        code = compile(self.tree, USER_FILENAME, "exec")
        self.globals = {"__name__": "__main__", "__builtins__": self.builtins}
        old_stdout = sys.stdout
        sys.stdout = self.output
        sys.settrace(self._global_trace)
        try:
            exec(code, self.globals)
        except TraceAbort:
            pass
        except BaseException as exc:  # noqa: BLE001 - user code may raise anything
            sys.settrace(None)
            self._on_uncaught(exc)
        else:
            sys.settrace(None)
            self._emit_finish()
        finally:
            sys.settrace(None)
            sys.stdout = old_stdout
        return self.result()

    def abort(self, reason: str) -> None:
        """Stop tracing because a resource limit was reached."""
        if self.finished:
            return
        messages = {
            "steps": f"Stopped after {self.limits.max_steps} steps. The program may contain an infinite loop, or it is too long to visualize.",
            "output": f"Stopped because the program printed more than {self.limits.max_output_chars} characters.",
            "depth": f"Stopped because more than {self.limits.max_stack_depth} function calls were active at once. This usually means a recursive function never reaches its base case.",
            "time": "Stopped because the program ran for too long. It may contain an infinite loop.",
        }
        sys.settrace(None)
        self.status = "limit"
        self.limit_reason = reason
        line = self.steps[-1]["line"] if self.steps else None
        self.error = {
            "phase": "limit",
            "type": "RecursionError" if reason == "depth" else "LimitExceeded",
            "message": messages.get(reason, reason),
            "line": line,
            "column": None,
            "hint": None,
        }
        self.finished = True
        if self.on_abort is not None:
            self.on_abort(self)
        raise TraceAbort(reason)

    def result(self) -> dict:
        self.finished = True
        return {
            "version": TRACE_FORMAT_VERSION,
            "status": self.status,
            "steps": self.steps,
            "output": self.output.getvalue(),
            "error": self.error,
            "truncated": self.status == "limit",
            "limitReason": self.limit_reason,
            "limits": asdict(self.limits),
            "stats": {
                "stepCount": len(self.steps),
                "durationMs": round((time.perf_counter() - self.started) * 1000, 1),
            },
        }

    # ------------------------------------------------------------------
    # sys.settrace callbacks
    # ------------------------------------------------------------------
    def _global_trace(self, frame, event, arg):
        if frame.f_code.co_filename != USER_FILENAME or self.finished:
            return None
        try:
            self._on_call(frame)
        except TraceAbort:
            raise
        except Exception as exc:  # pragma: no cover - engine bug safety net
            self._internal_error(exc)
        return self._local_trace

    def _local_trace(self, frame, event, arg):
        if self.finished:
            return None
        try:
            if event == "line":
                self._on_line(frame)
            elif event == "return":
                self._on_return(frame, arg)
            elif event == "exception":
                self._on_exception(frame, arg[1])
        except TraceAbort:
            raise
        except Exception as exc:  # pragma: no cover - engine bug safety net
            self._internal_error(exc)
        return self._local_trace

    def _internal_error(self, exc: Exception) -> None:
        sys.settrace(None)
        self.status = "internal"
        self.error = {
            "phase": "internal",
            "type": "TracerError",
            "message": f"The visualizer failed while tracing this program ({type(exc).__name__}). The steps recorded so far are shown.",
            "line": None,
            "column": None,
            "hint": None,
        }
        self.finished = True
        if self.on_abort is not None:
            self.on_abort(self)
        raise TraceAbort("internal")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_call(self, frame) -> None:
        code = frame.f_code
        if code.co_name == "<module>" and not self.frames:
            self.frames[id(frame)] = FrameInfo("global", "Global frame", frame, True)
            return
        depth = sum(1 for info in self.frames.values() if not info.is_global)
        if depth >= self.limits.max_stack_depth:
            self.abort("depth")
        self.frame_counter += 1
        name = code.co_name
        stmt = self.index.lookup(code.co_firstlineno)
        if isinstance(stmt, ast.ClassDef) and stmt.name == name:
            display = f"class {name} body"
        elif name == "<lambda>":
            display = "lambda"
        else:
            display = name
        info = FrameInfo(f"f{self.frame_counter}", display, frame, False)
        info.is_class_body = display.startswith("class ")
        self.frames[id(frame)] = info
        if info.is_class_body:
            return  # the class statement itself is explained on its own line

        caller = self._caller_info(frame)
        args = self._argument_values(frame)
        info.call_text = f"{display}({', '.join(f'{k}={explain.pyfmt(v, 25)}' for k, v in args)})"
        recursive = any(i.name == display and i is not info for i in self.frames.values())

        def build(changes, heap_changes, stack, heap):
            bullets = []
            if caller and caller.pending:
                bullets.append(f"Line {caller.pending.line} pauses while {display} runs.")
            bullets.append(f"A new frame is created for {display}. It has its own local variables, separate from the caller's.")
            for k, v in args:
                bullets.append(f"Parameter {k} receives the value {explain.pyfmt(v)}.")
            if recursive:
                bullets.append(f"{display} is already running further down the call stack, so this is a recursive call. Each call has its own copy of the parameters.")
            return f"Call {info.call_text}", bullets

        self._emit("call", frame, code.co_firstlineno, code.co_firstlineno, build)

    def _on_line(self, frame) -> None:
        info = self.frames.get(id(frame))
        if info is None:
            return
        info.unwinding = False  # an exception, if any, was caught in this frame
        line = frame.f_lineno
        stmt = self.index.lookup(line)
        if info.is_class_body and isinstance(stmt, ast.ClassDef) and line == stmt.lineno:
            return  # class body setup; the class statement is explained in the outer frame
        pending = info.pending
        if pending is not None and stmt is not None and pending.stmt is stmt:
            # Another line event inside the same multi-line statement.
            if not isinstance(stmt, LOOPS) or line != stmt.lineno:
                return
        if pending is not None:
            self._finish_pending(info, next_line=line)
        start = stmt.lineno if stmt is not None else line
        end = _header_end(stmt) if stmt is not None else line
        if isinstance(stmt, LOOPS):
            body_and_else = (stmt.lineno + 1, stmt.end_lineno or stmt.lineno)
            prev = info.last_line
            if prev is None or not (body_and_else[0] <= prev <= body_and_else[1]):
                info.loop_counts[stmt.lineno] = 0
        expr = explain.expression_for(stmt)
        if isinstance(stmt, ast.For) and info.loop_counts.get(stmt.lineno, 0) == 0:
            expr = stmt.iter
        pre = explain.pre_evaluate(expr, frame.f_locals, frame.f_globals, self.builtins)
        info.pending = Pending(stmt, start, end, pre, self.output.size)

    def _on_return(self, frame, value) -> None:
        info = self.frames.get(id(frame))
        if info is None:
            return
        try:
            if info.unwinding:
                return  # leaving the frame because of an exception; already reported
            pending = info.pending
            if info.is_global or info.is_class_body:
                if pending is not None:
                    self._finish_pending(info, next_line=None)
                return
            if pending is not None and not isinstance(pending.stmt, ast.Return):
                self._finish_pending(info, next_line=None)
                pending = None
            info.return_value = value
            info.pending = None
            caller = self._caller_info(frame)
            line = pending.line if pending else frame.f_lineno
            value_text = explain.pyfmt(value)

            def build(changes, heap_changes, stack, heap):
                bullets = list(pending.pre.ops) + pending.calls if pending else []
                if pending is None:
                    bullets.append(f"{info.name} reached the end of its body without a return statement, so it returns None.")
                where = f"line {caller.pending.line}" if caller and caller.pending else "the caller"
                bullets.append(f"{info.name} returns {value_text} to {where}.")
                bullets.append(f"The frame for {info.name} is removed; its local variables disappear.")
                return f"{info.call_text} returns {value_text}", bullets

            self._emit("return", frame, line, line, build)
            if caller is not None and caller.pending is not None:
                caller.pending.calls.append(f"{info.call_text} returned {value_text}.")
        finally:
            self.frames.pop(id(frame), None)

    def _on_exception(self, frame, exc: BaseException) -> None:
        info = self.frames.get(id(frame))
        if info is None or isinstance(exc, TraceAbort):
            return
        pending = info.pending
        info.pending = None
        info.unwinding = True
        if id(exc) in self.reported_exceptions:
            return  # propagating from a callee; reported where it was raised
        line = pending.line if pending else frame.f_lineno
        end = pending.end_line if pending else line
        self.reported_exceptions[id(exc)] = (exc, len(self.steps))
        exc_type = type(exc).__name__
        message = _exception_message(exc)

        def build(changes, heap_changes, stack, heap):
            bullets = list(pending.pre.ops) if pending else []
            bullets.extend(pending.calls if pending else [])
            bullets.extend(explain.exception_bullets(exc_type, message))
            return f"{exc_type} raised on line {line}", bullets

        self._emit("exception", frame, line, end, build,
                   extra={"exception": {"type": exc_type, "message": message, "line": line, "uncaught": False}})

    def _finish_pending(self, info: FrameInfo, next_line: int | None) -> None:
        pending = info.pending
        info.pending = None
        info.unwinding = False
        info.last_line = pending.line
        stmt = pending.stmt
        text = explain.header_text(self.lines, stmt, pending.line)
        new_output = self.output.getvalue()[pending.output_len:]
        extra: dict = {}
        summary_override: str | None = None
        flow: list[str] = []

        if isinstance(stmt, ast.If):
            body = block_of(stmt.body)
            taken = body.contains(next_line) if body else False
            extra["condition"] = {"result": taken}
            if taken:
                flow.append("The condition is True, so Python runs the indented block below it.")
            else:
                orelse = stmt.orelse
                if orelse and isinstance(orelse[0], ast.If) and orelse[0].lineno == next_line and len(orelse) == 1 and _is_elif(self.lines, orelse[0]):
                    flow.append("The condition is False, so Python skips this block and checks the next elif.")
                elif orelse and block_of(orelse).contains(next_line):
                    flow.append("The condition is False, so Python skips this block and runs the else block.")
                else:
                    flow.append("The condition is False, so Python skips the indented block.")
        elif isinstance(stmt, ast.While):
            body = block_of(stmt.body)
            taken = body.contains(next_line) if body else False
            extra["condition"] = {"result": taken}
            if taken:
                count = info.loop_counts.get(stmt.lineno, 0) + 1
                info.loop_counts[stmt.lineno] = count
                extra["loop"] = {"line": stmt.lineno, "iteration": count, "ended": False}
                summary_override = f"While loop, iteration {count}: condition is True"
                flow.append(f"The condition is True, so the loop body runs (iteration {count}).")
            else:
                done = info.loop_counts.get(stmt.lineno, 0)
                extra["loop"] = {"line": stmt.lineno, "iteration": done, "ended": True}
                summary_override = "While loop ends: condition is False"
                flow.append(f"The condition is False, so the loop stops after {done} iteration{'s' if done != 1 else ''}.")
        elif isinstance(stmt, ast.For):
            body = block_of(stmt.body)
            taken = body.contains(next_line) if body else False
            if taken:
                count = info.loop_counts.get(stmt.lineno, 0) + 1
                info.loop_counts[stmt.lineno] = count
                extra["loop"] = {"line": stmt.lineno, "iteration": count, "ended": False}
                target = explain._src(stmt.target)
                summary_override = f"For loop, iteration {count}: next value of {target}"
                if count == 1 and pending.pre.evaluated:
                    flow.append(f"The loop goes through {explain.pyfmt(pending.pre.value)} one item at a time.")
                flow.append(f"Python takes the next item and assigns it to {target} (iteration {count}).")
            else:
                done = info.loop_counts.get(stmt.lineno, 0)
                extra["loop"] = {"line": stmt.lineno, "iteration": done, "ended": True}
                summary_override = "For loop ends: no more items"
                if done == 0:
                    flow.append("The sequence is empty, so the loop body never runs.")
                else:
                    flow.append(f"There are no more items, so the loop ends after {done} iteration{'s' if done != 1 else ''}.")
        elif isinstance(stmt, ast.Assert):
            flow.append("The assertion holds (its condition is True), so the program continues.")

        ops = list(pending.pre.ops)
        if isinstance(stmt, ast.For) and not (extra.get("loop", {}).get("iteration") == 1):
            ops = []  # the iterable is only evaluated when the loop starts

        def build(changes, heap_changes, stack, heap):
            bullets = list(explain.static_bullets(stmt))
            bullets.extend(ops)
            bullets.extend(pending.calls)
            bullets.extend(flow)
            mentioned = {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name)} if stmt is not None else set()
            bullets.extend(explain.describe_changes(changes, heap_changes, stack, heap, self.prev_heap, mentioned))
            if new_output:
                shown = new_output if len(new_output) <= 120 else new_output[:119] + "…"
                bullets.append(f"Printed to the output: {shown.rstrip(chr(10))!r}" if shown.strip() else "Printed an empty line to the output.")
            if not bullets:
                bullets.append("This line ran; it did not change any variables.")
            return summary_override or explain.summarize_statement(stmt, text), bullets

        self._emit("line", info.frame, pending.line, pending.end_line, build, extra=extra)

    def _on_uncaught(self, exc: BaseException) -> None:
        exc_type = type(exc).__name__
        message = _exception_message(exc)
        reported = self.reported_exceptions.get(id(exc))
        line = None
        if reported is not None:
            step = self.steps[reported[1]]
            step["exception"]["uncaught"] = True
            step["explanation"].append("Nothing caught this exception, so the program stops here.")
            line = step["line"]
        else:
            tb = exc.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code.co_filename == USER_FILENAME:
                    line = tb.tb_lineno
                tb = tb.tb_next
        self.status = "error"
        self.error = {
            "phase": "runtime",
            "type": exc_type,
            "message": message,
            "line": line,
            "column": None,
            "hint": explain.EXCEPTION_HINTS.get(exc_type),
        }

    def _emit_finish(self) -> None:
        global_frame = [("global", "Global frame", None, self.globals, True, NO_VALUE)]
        stack, heap = self.encoder.snapshot(global_frame)
        changes, heap_changes = diff_snapshots(self.prev_stack, self.prev_heap, stack, heap)
        lines_out = self.output.getvalue().count("\n")
        bullets = ["Every line has run and the program has ended."]
        bullets.append(f"It printed {lines_out} line{'s' if lines_out != 1 else ''} of output." if lines_out else "It did not print anything.")
        self._append_step("finish", None, None, "global", "Global frame", stack, heap, changes, heap_changes,
                          "Program finished", bullets, {})

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------
    def _caller_info(self, frame) -> FrameInfo | None:
        back = frame.f_back
        while back is not None:
            info = self.frames.get(id(back))
            if info is not None:
                return info
            back = back.f_back
        return None

    def _argument_values(self, frame) -> list[tuple[str, Any]]:
        code = frame.f_code
        count = code.co_argcount + code.co_kwonlyargcount
        count += bool(code.co_flags & 0x04) + bool(code.co_flags & 0x08)
        local_vars = frame.f_locals
        return [(n, local_vars[n]) for n in code.co_varnames[:count] if n in local_vars]

    def _live_frames(self, frame, line_override: int | None = None) -> list[tuple]:
        chain = []
        f = frame
        while f is not None:
            info = self.frames.get(id(f))
            if info is not None:
                chain.append((info, f))
            f = f.f_back
        chain.reverse()
        result = []
        for info, f in chain:
            if f is frame and line_override is not None:
                line = line_override
            else:
                line = info.pending.line if info.pending else f.f_lineno
            variables = f.f_globals if info.is_global else f.f_locals
            result.append((info.id, info.name, line, variables, info.is_global, info.return_value))
        return result

    def _emit(self, event: str, frame, line: int | None, end_line: int | None,
              build: Callable[..., tuple[str, list[str]]], extra: dict | None = None) -> None:
        stack, heap = self.encoder.snapshot(self._live_frames(frame, line))
        changes, heap_changes = diff_snapshots(self.prev_stack, self.prev_heap, stack, heap)
        summary, bullets = build(changes, heap_changes, stack, heap)
        info = self.frames.get(id(frame))
        self._append_step(event, line, end_line, info.id if info else "global", info.name if info else "",
                          stack, heap, changes, heap_changes, summary, bullets, extra or {})

    def _append_step(self, event, line, end_line, frame_id, func_name, stack, heap, changes, heap_changes,
                     summary, bullets, extra) -> None:
        step = {
            "index": len(self.steps),
            "eventId": f"e{len(self.steps) + 1}",
            "event": event,
            "line": line,
            "endLine": end_line,
            "frameId": frame_id,
            "funcName": func_name,
            "stack": stack,
            "heap": heap,
            "outputLength": self.output.size,
            "changes": changes,
            "heapChanges": heap_changes,
            "summary": summary,
            "explanation": bullets,
            "exception": None,
            "condition": None,
            "loop": None,
        }
        step.update(extra)
        self.steps.append(step)
        self.prev_stack, self.prev_heap = stack, heap
        if len(self.steps) >= self.limits.max_steps:
            self.abort("steps")


def _header_end(stmt: ast.AST) -> int:
    from .statements import header_end

    return header_end(stmt)


def _is_elif(lines: list[str], node: ast.If) -> bool:
    text = lines[node.lineno - 1].lstrip() if node.lineno - 1 < len(lines) else ""
    return text.startswith("elif")


def _exception_message(exc: BaseException) -> str:
    try:
        text = str(exc)
    except Exception:
        text = ""
    return text if len(text) <= 300 else text[:299] + "…"


def error_result(err: ValidationError | dict, limits: TraceLimits | None = None) -> dict:
    payload = err.to_dict() if isinstance(err, ValidationError) else dict(err)
    payload.setdefault("hint", None)
    status = "limit" if payload.get("phase") == "limit" else "error"
    return {
        "version": TRACE_FORMAT_VERSION,
        "status": status,
        "steps": [],
        "output": "",
        "error": payload,
        "truncated": False,
        "limitReason": None,
        "limits": asdict(limits or TraceLimits()),
        "stats": {"stepCount": 0, "durationMs": 0.0},
    }


def fit_to_size(result: dict, max_bytes: int) -> str:
    """Serialize a result, dropping trailing steps if it exceeds max_bytes."""
    text = json.dumps(result, separators=(",", ":"))
    if len(text) <= max_bytes or not result["steps"]:
        return text
    steps = result["steps"]
    lo, hi = 0, len(steps)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        size = len(json.dumps(steps[:mid], separators=(",", ":")))
        if size <= max_bytes - 20_000:
            lo = mid
        else:
            hi = mid - 1
    trimmed = dict(result)
    trimmed["steps"] = steps[:lo]
    trimmed["truncated"] = True
    trimmed["status"] = "limit"
    trimmed["limitReason"] = "size"
    trimmed["error"] = {
        "phase": "limit",
        "type": "LimitExceeded",
        "message": f"The trace was too large to send, so only the first {lo} steps are shown.",
        "line": None,
        "column": None,
        "hint": None,
    }
    trimmed["stats"] = dict(result["stats"], stepCount=lo)
    return json.dumps(trimmed, separators=(",", ":"))


def trace_code(source: str, limits: TraceLimits | None = None) -> dict:
    """Validate and trace ``source`` in the current process.

    Used by tests and by the isolated runner. Never call this from the web
    server process with untrusted code; use ``app.sandbox`` instead.
    """
    try:
        tracer = Tracer(source, limits)
    except ValidationError as err:
        return error_result(err, limits)
    return tracer.run()
