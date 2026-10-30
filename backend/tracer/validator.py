"""Static validation of submitted code against the supported Python subset.

This is *not* a security boundary (that is the isolated child process, see
``app/sandbox.py``). It exists so that unsupported constructs produce a clear
message instead of a misleading visualization, and as defence in depth against
the most common introspection escape routes.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

MAX_SOURCE_CHARS = 20_000
MAX_SOURCE_LINES = 500

ALLOWED_IMPORTS = {"math", "random", "string"}

# Names that would let code reach outside the visualized program.
FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "breakpoint", "input", "memoryview",
    "help", "exit", "quit", "dir",
}

UNSUPPORTED: dict[type, str] = {
    ast.AsyncFunctionDef: "async functions",
    ast.AsyncFor: "async for loops",
    ast.AsyncWith: "async with statements",
    ast.Await: "await expressions",
    ast.With: "with statements",
    ast.Yield: "generators (yield)",
    ast.YieldFrom: "generators (yield from)",
    ast.GeneratorExp: "generator expressions (use a list comprehension instead)",
    ast.Match: "match statements",
}
if hasattr(ast, "TryStar"):
    UNSUPPORTED[ast.TryStar] = "except* (exception groups)"
if hasattr(ast, "TypeAlias"):
    UNSUPPORTED[ast.TypeAlias] = "type aliases"


@dataclass
class ValidationError(Exception):
    phase: str  # "syntax" | "unsupported" | "input"
    type: str
    message: str
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "type": self.type,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def validate_source(source: str) -> ast.Module:
    if not isinstance(source, str):
        raise ValidationError("input", "InputError", "Code must be a string.")
    if not source.strip():
        raise ValidationError("input", "InputError", "There is no code to run. Type some Python first.")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValidationError("input", "InputError", f"Code is too long (limit is {MAX_SOURCE_CHARS} characters).")
    if source.count("\n") + 1 > MAX_SOURCE_LINES:
        raise ValidationError("input", "InputError", f"Code has too many lines (limit is {MAX_SOURCE_LINES}).")
    if "\x00" in source:
        raise ValidationError("input", "InputError", "Code contains a null byte.")

    try:
        tree = ast.parse(source, filename="<user_code>", mode="exec")
    except SyntaxError as exc:
        raise ValidationError(
            "syntax",
            type(exc).__name__,
            exc.msg or "invalid syntax",
            exc.lineno,
            exc.offset,
        ) from None
    except (ValueError, MemoryError, RecursionError) as exc:
        raise ValidationError("syntax", "SyntaxError", f"Could not parse code: {exc}") from None

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        col = getattr(node, "col_offset", None)
        col = col + 1 if col is not None else None

        def fail(message: str) -> None:
            raise ValidationError("unsupported", "UnsupportedFeature", message, line, col)

        for kind, label in UNSUPPORTED.items():
            if isinstance(node, kind):
                fail(f"This visualizer does not support {label} yet.")

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    fail(f"Importing '{alias.name}' is not allowed. Allowed modules: {', '.join(sorted(ALLOWED_IMPORTS))}.")
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module not in ALLOWED_IMPORTS:
                fail(f"Importing from '{node.module}' is not allowed. Allowed modules: {', '.join(sorted(ALLOWED_IMPORTS))}.")
            if any(alias.name == "*" for alias in node.names):
                fail("'from module import *' is not supported; import names explicitly.")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                if node.id == "input":
                    fail("input() is not supported: the visualizer cannot pause for keyboard input. Assign a value to a variable instead.")
                fail(f"'{node.id}' is not available in the visualizer.")
            if _dunder(node.id) and node.id != "__name__":
                fail(f"Special name '{node.id}' is not supported.")
        elif isinstance(node, ast.Attribute):
            if _dunder(node.attr) and node.attr not in {"__init__", "__name__"}:
                fail(f"Accessing special attribute '{node.attr}' is not supported.")
        elif isinstance(node, ast.ClassDef):
            if node.decorator_list or node.keywords:
                fail("Class decorators and metaclasses are not supported.")
        elif isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                fail("Function decorators are not supported yet.")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                if _dunder(name):
                    fail(f"Special name '{name}' is not supported.")

    return tree
