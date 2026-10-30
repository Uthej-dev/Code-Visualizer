"""Beginner-friendly explanations built only from observed execution data.

Two sources of truth feed every explanation:

1. **Pre-evaluation** (``SafeEvaluator``): just before a line runs, pure
   sub-expressions made only of builtin values (numbers, strings, lists, …)
   are re-computed with the frame's real values so the explanation can show
   "Read a → 3, Compute 3 + 4 → 7". Anything that could have side effects or
   run user code (calls to user functions, attribute access, methods, …)
   makes the evaluator bail out; the explanation then falls back to a
   generic description instead of guessing.
2. **Observed changes**: after the line runs, the snapshot diff (variables
   created / changed / mutated, output printed, functions that returned)
   describes what actually happened.
"""

from __future__ import annotations

import ast
import builtins as _builtins
import io
import operator
import tokenize
from dataclasses import dataclass, field
from typing import Any

from .diff import member_label
from .serialize import short_repr

PLAIN_SCALARS = (int, float, str, bool, type(None), complex, range)
PLAIN_CONTAINERS = (list, tuple, dict, set, frozenset)

BIN_OPS = {
    ast.Add: ("+", operator.add),
    ast.Sub: ("-", operator.sub),
    ast.Mult: ("*", operator.mul),
    ast.Div: ("/", operator.truediv),
    ast.FloorDiv: ("//", operator.floordiv),
    ast.Mod: ("%", operator.mod),
    ast.Pow: ("**", operator.pow),
    ast.LShift: ("<<", operator.lshift),
    ast.RShift: (">>", operator.rshift),
    ast.BitAnd: ("&", operator.and_),
    ast.BitOr: ("|", operator.or_),
    ast.BitXor: ("^", operator.xor),
}
CMP_OPS = {
    ast.Eq: ("==", operator.eq),
    ast.NotEq: ("!=", operator.ne),
    ast.Lt: ("<", operator.lt),
    ast.LtE: ("<=", operator.le),
    ast.Gt: (">", operator.gt),
    ast.GtE: (">=", operator.ge),
    ast.In: ("in", lambda a, b: a in b),
    ast.NotIn: ("not in", lambda a, b: a not in b),
    ast.Is: ("is", operator.is_),
    ast.IsNot: ("is not", operator.is_not),
}
PURE_BUILTINS = {"len", "abs", "min", "max", "sum", "round", "str", "int", "float", "bool", "sorted", "type"}

EXCEPTION_HINTS = {
    "ZeroDivisionError": "You tried to divide by zero, which is not allowed in mathematics or in Python.",
    "NameError": "The program used a name that has not been defined yet. Check the spelling, and make sure the variable is assigned before it is used.",
    "IndexError": "The program asked for a position that does not exist in the list. Valid indexes go from 0 to len(list) - 1.",
    "KeyError": "The program looked up a key that is not in the dictionary. Use `in` to check first, or dict.get().",
    "TypeError": "An operation was used with a value of the wrong type, for example adding a number to a string.",
    "ValueError": "A value had the right type but an unsuitable content, for example int('hello').",
    "AttributeError": "The program asked for an attribute or method that this kind of value does not have.",
    "RecursionError": "A function called itself too many times. Recursive functions need a base case that stops the recursion.",
    "UnboundLocalError": "A local variable was used before it was given a value inside the function.",
    "AssertionError": "An assert statement found that its condition was False.",
    "StopIteration": "next() was called on an iterator that has no more items.",
    "OverflowError": "A number became too large to represent.",
}


class Unsafe(Exception):
    """The expression cannot be evaluated without risking side effects."""


class EvalRaised(Exception):
    def __init__(self, exc: BaseException):
        self.exc = exc


def is_plain(value: Any, budget: list[int] | None = None) -> bool:
    """True if value is built only from builtin data types (no user objects)."""
    if budget is None:
        budget = [2000]
    budget[0] -= 1
    if budget[0] < 0:
        return False
    t = type(value)
    if t in PLAIN_SCALARS:
        return True
    if t in (list, tuple, set, frozenset):
        return all(is_plain(v, budget) for v in value)
    if t is dict:
        return all(is_plain(k, budget) and is_plain(v, budget) for k, v in value.items())
    return False


def pyfmt(value: Any, limit: int = 60) -> str:
    """Short display string for a live Python value (never calls user code)."""
    t = type(value)
    if t in PLAIN_SCALARS:
        return short_repr(value, limit)
    if t in PLAIN_CONTAINERS and is_plain(value, [200]):
        return short_repr(value, limit)
    if t in PLAIN_CONTAINERS:
        return f"a {t.__name__} of {len(value)} items"
    if callable(value) and hasattr(value, "__name__"):
        return f"function {value.__name__}"
    return f"a {t.__name__} object"


def _guard_size(op: type, left: Any, right: Any) -> None:
    if op is ast.Mult:
        for seq, n in ((left, right), (right, left)):
            if type(seq) in (str, list, tuple) and type(n) in (int, bool) and len(seq) * max(n, 0) > 100_000:
                raise Unsafe
    if op is ast.Pow and type(left) is int and type(right) is int:
        if right > 0 and abs(left) > 1 and left.bit_length() * right > 64_000:
            raise Unsafe
    if op is ast.LShift and type(right) is int and right > 64_000:
        raise Unsafe


@dataclass
class SafeEvaluator:
    env_locals: dict
    env_globals: dict
    builtins_dict: dict
    ops: list[str] = field(default_factory=list)
    max_ops: int = 12

    def note(self, text: str) -> None:
        if len(self.ops) < self.max_ops:
            self.ops.append(text)
        elif len(self.ops) == self.max_ops:
            self.ops.append("…")

    def lookup(self, name: str) -> Any:
        if name in self.env_locals:
            return self.env_locals[name]
        if name in self.env_globals:
            return self.env_globals[name]
        raise Unsafe

    def plain(self, value: Any) -> Any:
        if not is_plain(value):
            raise Unsafe
        return value

    def ev(self, node: ast.expr) -> Any:
        try:
            return self._ev(node)
        except RecursionError:
            raise Unsafe from None

    def _ev(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return self.plain(node.value)
        if isinstance(node, ast.Name):
            value = self.plain(self.lookup(node.id))
            self.note(f"Read {node.id} → {pyfmt(value)}")
            return value
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            if any(isinstance(e, ast.Starred) for e in node.elts):
                raise Unsafe
            items = [self._ev(e) for e in node.elts]
            return {ast.List: list, ast.Tuple: tuple, ast.Set: set}[type(node)](items)
        if isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise Unsafe
            return {self._ev(k): self._ev(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.BinOp):
            left, right = self._ev(node.left), self._ev(node.right)
            sym, fn = BIN_OPS.get(type(node.op), (None, None))
            if fn is None:
                raise Unsafe
            _guard_size(type(node.op), left, right)
            result = self._apply(fn, (left, right), f"{pyfmt(left)} {sym} {pyfmt(right)}")
            self.note(f"Compute {pyfmt(left)} {sym} {pyfmt(right)} → {pyfmt(result)}")
            return self.plain(result)
        if isinstance(node, ast.UnaryOp):
            operand = self._ev(node.operand)
            if isinstance(node.op, ast.Not):
                result = not operand
                self.note(f"Compute not {pyfmt(operand)} → {result}")
                return result
            sym, fn = {ast.USub: ("-", operator.neg), ast.UAdd: ("+", operator.pos), ast.Invert: ("~", operator.invert)}[type(node.op)]
            result = self._apply(fn, (operand,), f"{sym}{pyfmt(operand)}")
            if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
                return result  # a negative literal such as -1 is not an operation
            self.note(f"Compute {sym}{pyfmt(operand)} → {pyfmt(result)}")
            return self.plain(result)
        if isinstance(node, ast.Compare):
            left = self._ev(node.left)
            result = True
            for op, comp in zip(node.ops, node.comparators):
                right = self._ev(comp)
                sym, fn = CMP_OPS[type(op)]
                part = self._apply(fn, (left, right), f"{pyfmt(left)} {sym} {pyfmt(right)}")
                self.note(f"Compare {pyfmt(left)} {sym} {pyfmt(right)} → {part}")
                if not part:
                    result = False
                    break
                left = right
            return result
        if isinstance(node, ast.BoolOp):
            word = "and" if isinstance(node.op, ast.And) else "or"
            value = None
            for i, sub in enumerate(node.values):
                value = self._ev(sub)
                truthy = bool(value)
                last = i == len(node.values) - 1
                if not last and ((word == "and" and not truthy) or (word == "or" and truthy)):
                    self.note(f"'{word}' stops early: {pyfmt(value)} is {'truthy' if truthy else 'falsy'}, so the result is {pyfmt(value)}")
                    return value
            if len(node.values) > 1:
                self.note(f"Result of '{word}' → {pyfmt(value)}")
            return value
        if isinstance(node, ast.IfExp):
            test = self._ev(node.test)
            branch = node.body if test else node.orelse
            self.note(f"Condition {pyfmt(test)} is {'truthy' if test else 'falsy'} → use the {'first' if test else 'else'} value")
            return self._ev(branch)
        if isinstance(node, ast.Subscript):
            container = self._ev(node.value)
            if isinstance(node.slice, ast.Slice):
                parts = [self._ev(p) if p is not None else None for p in (node.slice.lower, node.slice.upper, node.slice.step)]
                key: Any = slice(*parts)
                key_text = ":".join("" if p is None else pyfmt(p) for p in parts[: 3 if parts[2] is not None else 2])
            else:
                key = self._ev(node.slice)
                key_text = pyfmt(key)
            if type(container) not in (list, tuple, str, dict, range):
                raise Unsafe
            result = self._apply(operator.getitem, (container, key), _src(node))
            self.note(f"Look up {_src(node.value)}[{key_text}] → {pyfmt(result)}")
            return self.plain(result)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords or node.func.id not in PURE_BUILTINS:
                raise Unsafe
            if any(isinstance(a, ast.Starred) for a in node.args):
                raise Unsafe
            fn = self._resolve_builtin(node.func.id)
            args = [self._ev(a) for a in node.args]
            if node.func.id == "type":
                if len(args) != 1:
                    raise Unsafe
                result = type(args[0])
                self.note(f"type({pyfmt(args[0])}) → {result.__name__}")
                return result
            if node.func.id in ("str", "int") and args and type(args[0]) in (int, str) and len(str(args[0])) > 4000:
                raise Unsafe
            result = self._apply(fn, tuple(args), f"{node.func.id}(…)")
            self.note(f"Call {node.func.id}({', '.join(pyfmt(a, 30) for a in args)}) → {pyfmt(result)}")
            return self.plain(result)
        raise Unsafe

    def _resolve_builtin(self, name: str) -> Any:
        if name in self.env_locals or name in self.env_globals:
            raise Unsafe  # shadowed by a user definition
        fn = self.builtins_dict.get(name)
        if fn is None or fn is not getattr(_builtins, name, None):
            raise Unsafe
        return fn

    def _apply(self, fn, args: tuple, text: str) -> Any:
        try:
            return fn(*args)
        except (ArithmeticError, LookupError, TypeError, ValueError) as exc:
            self.note(f"Compute {text} → raises {type(exc).__name__}")
            raise EvalRaised(exc) from None


def _src(node: ast.AST) -> str:
    try:
        text = ast.unparse(node)
    except Exception:  # pragma: no cover
        return "…"
    return text if len(text) <= 60 else text[:59] + "…"


@dataclass
class PreInfo:
    ops: list[str]
    value: Any = None
    evaluated: bool = False
    raised: str | None = None


def pre_evaluate(expr: ast.expr | None, env_locals: dict, env_globals: dict, builtins_dict: dict) -> PreInfo:
    if expr is None:
        return PreInfo(ops=[])
    ev = SafeEvaluator(env_locals, env_globals, builtins_dict)
    try:
        value = ev.ev(expr)
        return PreInfo(ops=ev.ops, value=value, evaluated=True)
    except EvalRaised as raised:
        return PreInfo(ops=ev.ops, raised=type(raised.exc).__name__)
    except (Unsafe, KeyError, AttributeError):
        return PreInfo(ops=[])


def expression_for(stmt: ast.AST | None) -> ast.expr | None:
    """The expression a statement evaluates when its line runs."""
    if isinstance(stmt, ast.Assign):
        return stmt.value
    if isinstance(stmt, ast.AnnAssign):
        return stmt.value
    if isinstance(stmt, ast.AugAssign):
        target = stmt.target
        if isinstance(target, ast.Name):
            load = ast.Name(id=target.id, ctx=ast.Load())
        elif isinstance(target, ast.Subscript):
            load = ast.Subscript(value=target.value, slice=target.slice, ctx=ast.Load())
        else:
            return None
        return ast.copy_location(ast.BinOp(left=load, op=stmt.op, right=stmt.value), stmt)
    if isinstance(stmt, (ast.If, ast.While, ast.Assert)):
        return stmt.test
    if isinstance(stmt, ast.Return):
        return stmt.value
    if isinstance(stmt, ast.Expr):
        call = stmt.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "print":
            # Pre-evaluate each printed argument; print itself is observed via output.
            if not call.keywords and len(call.args) == 1:
                return call.args[0]
            return ast.Tuple(elts=list(call.args), ctx=ast.Load()) if not call.keywords else None
        return None
    return None


def _strip_comment(text: str) -> str:
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                return text[: tok.start[1]].rstrip()
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    return text


def header_text(source_lines: list[str], stmt: ast.AST | None, line: int) -> str:
    text = source_lines[line - 1].strip() if 0 < line <= len(source_lines) else ""
    text = _strip_comment(text)
    return text if len(text) <= 70 else text[:69] + "…"


def summarize_statement(stmt: ast.AST | None, text: str) -> str:
    """One-line headline for a statement, independent of runtime values."""
    if isinstance(stmt, ast.Assign):
        return f"Assignment: {text}"
    if isinstance(stmt, ast.AugAssign):
        return f"Update: {text}"
    if isinstance(stmt, ast.AnnAssign):
        return f"Assignment: {text}"
    if isinstance(stmt, ast.If):
        return f"Check condition: {_src(stmt.test)}"
    if isinstance(stmt, ast.While):
        return f"Check while-loop condition: {_src(stmt.test)}"
    if isinstance(stmt, ast.For):
        return f"For loop: {text.rstrip(':')}"
    if isinstance(stmt, ast.FunctionDef):
        return f"Define function {stmt.name}()"
    if isinstance(stmt, ast.ClassDef):
        return f"Define class {stmt.name}"
    if isinstance(stmt, ast.Return):
        return f"Return statement: {text}"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        if isinstance(func, ast.Name) and func.id == "print":
            return "Print to the output"
        return f"Call {_src(func)}(…)"
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return f"Import: {text}"
    if isinstance(stmt, ast.Pass):
        return "pass — do nothing"
    if isinstance(stmt, ast.Break):
        return "break — leave the loop"
    if isinstance(stmt, ast.Continue):
        return "continue — go to the next loop iteration"
    if isinstance(stmt, ast.Try):
        return "Enter a try block"
    if isinstance(stmt, ast.ExceptHandler):
        return f"Handle the exception: {text.rstrip(':')}"
    if isinstance(stmt, ast.Raise):
        return "Raise an exception"
    if isinstance(stmt, ast.Assert):
        return f"Assert: {_src(stmt.test)}"
    if isinstance(stmt, ast.Delete):
        return f"Delete: {text}"
    if isinstance(stmt, (ast.Global, ast.Nonlocal)):
        return text
    return f"Run line: {text}"


def static_bullets(stmt: ast.AST | None) -> list[str]:
    if isinstance(stmt, ast.FunctionDef):
        params = ", ".join(a.arg for a in stmt.args.args) or "no parameters"
        return [
            f"Python creates a function object named {stmt.name} (parameters: {params}).",
            "The body is stored, not run. It runs each time the function is called.",
        ]
    if isinstance(stmt, ast.ClassDef):
        return [f"Python creates the class {stmt.name}, a blueprint for making objects."]
    if isinstance(stmt, ast.Try):
        return ["If an error happens inside the try block, Python jumps to a matching except block instead of stopping."]
    if isinstance(stmt, ast.ExceptHandler):
        return ["An exception was raised in the try block and this except clause matches it, so its block runs."]
    if isinstance(stmt, ast.Break):
        return ["The loop stops immediately; Python continues after the loop."]
    if isinstance(stmt, ast.Continue):
        return ["The rest of this iteration is skipped."]
    if isinstance(stmt, ast.Pass):
        return ["pass is a placeholder that does nothing."]
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return ["The module's functions and values become available to the program."]
    return []


# ---------------------------------------------------------------------------
# Describing encoded values and observed changes
# ---------------------------------------------------------------------------

def describe_value(value: dict | None, heap: dict, limit: int = 50) -> str:
    if value is None:
        return "nothing"
    if value["kind"] == "prim":
        return value["repr"]
    obj = heap.get(value["id"])
    if obj is None:
        return "an object"
    return preview_object(obj, heap, limit)


def preview_object(obj: dict, heap: dict, limit: int = 50, depth: int = 0) -> str:
    t = obj["type"]

    def inner(v: dict) -> str:
        if v["kind"] == "prim":
            return v["repr"]
        child = heap.get(v["id"])
        if child is None or depth >= 1:
            return "…"
        return preview_object(child, heap, limit, depth + 1)

    if t in ("list", "tuple", "set", "frozenset"):
        open_, close = {"list": "[]", "tuple": "()", "set": "{}", "frozenset": "{}"}[t]
        body = ", ".join(inner(v) for v in obj["items"])
        if obj.get("truncated"):
            body += ", …"
        if t == "tuple" and len(obj["items"]) == 1:
            body += ","
        if t in ("set", "frozenset") and not obj["items"]:
            text = "set()"
        else:
            text = open_ + body + close
    elif t in ("dict", "instance"):
        body = ", ".join(f"{inner(e['key'])}: {inner(e['value'])}" for e in obj["entries"])
        text = "{" + body + "}" if t == "dict" else f"{obj['className']} object"
    elif t == "function":
        text = f"function {obj['name']}({', '.join(obj['params'])})"
    elif t == "class":
        text = f"class {obj['name']}"
    else:
        text = obj.get("repr", "object")
    return text if len(text) <= limit else text[: limit - 1] + "…"


TYPE_NOUNS = {
    "list": "list", "tuple": "tuple", "dict": "dictionary", "set": "set", "frozenset": "frozenset",
    "instance": "object", "function": "function", "class": "class",
}


def describe_changes(changes: list[dict], heap_changes: list[dict], stack: list[dict], heap: dict, prev_heap: dict,
                     mentioned: set[str] | None = None) -> list[str]:
    bullets: list[str] = []
    if mentioned:
        # When one object changes under several names, describe it through the
        # name the statement actually used (e.g. backup.remove(...)).
        changes = sorted(changes, key=lambda ch: ch["kind"] == "mutated" and ch["name"] not in mentioned)
    explained_objects: set[str] = set()
    holders: dict[str, list[str]] = {}
    for frame in stack:
        for var in frame["locals"]:
            if var["value"]["kind"] == "ref":
                holders.setdefault(var["value"]["id"], []).append(var["name"])

    for ch in changes:
        name, kind = ch["name"], ch["kind"]
        after, before = ch["after"], ch["before"]
        if kind == "created":
            if after["kind"] == "ref":
                obj = heap.get(after["id"], {})
                noun = TYPE_NOUNS.get(obj.get("type", ""), "object")
                others = [n for n in holders.get(after["id"], []) if n != name]
                if after["id"] in prev_heap and others:
                    bullets.append(
                        f"Create variable {name}. It refers to the same {noun} as {', '.join(others)} — no copy is made, both names share one object."
                    )
                elif obj.get("type") == "function":
                    continue  # explained by the def statement
                else:
                    bullets.append(f"Create variable {name}, which refers to {_article(noun)} {noun}: {describe_value(after, heap)}")
            else:
                bullets.append(f"Create variable {name} and store {after['repr']} in it.")
        elif kind == "rebound":
            if before["kind"] == "prim" and after["kind"] == "prim":
                bullets.append(f"Change {name} from {before['repr']} to {after['repr']}.")
            elif after["kind"] == "ref":
                obj = heap.get(after["id"], {})
                noun = TYPE_NOUNS.get(obj.get("type", ""), "object")
                bullets.append(f"{name} now refers to a different {noun}: {describe_value(after, heap)} (the variable was re-bound, not modified in place).")
            else:
                bullets.append(f"{name} now holds {after['repr']} instead of an object.")
        elif kind == "mutated":
            if after["id"] in explained_objects:
                continue  # same object already described through another name
            obj = heap.get(after["id"], {})
            explained_objects.add(after["id"])
            change = next((h for h in heap_changes if h["id"] == after["id"]), None)
            bullets.append(_mutation_text(name, obj, change, heap, holders))
        elif kind == "removed":
            bullets.append(f"Variable {name} is deleted.")

    for hc in heap_changes:
        if hc["kind"] != "mutated" or hc["id"] in explained_objects:
            continue
        obj = heap.get(hc["id"])
        if obj is None:
            continue
        names = holders.get(hc["id"])
        if names:
            continue  # already covered by a variable change in this frame or not visible
        bullets.append(_mutation_text(None, obj, hc, heap, holders))
    return bullets


def _mutation_text(name: str | None, obj: dict, change: dict | None, heap: dict, holders: dict) -> str:
    noun = TYPE_NOUNS.get(obj.get("type", ""), "object")
    subject = f"The {noun} {name}" if name else f"{_article(noun).capitalize()} {noun} stored inside another object"
    details: list[str] = []
    if change:
        members = _members_by_key(obj)
        for key in change["added"][:3]:
            details.append(f"added {_member_desc(obj, key, members, heap)}")
        for key in change["changed"][:3]:
            details.append(f"changed {_member_desc(obj, key, members, heap)}")
        if change["removed"]:
            labels = ", ".join(_bracket(obj, member_label(obj, k)) for k in change["removed"][:3])
            details.append(f"removed {labels}")
    shared = [n for n in holders.get(obj.get("id", ""), []) if n != name]
    text = f"{subject} was modified in place"
    if details:
        text += ": " + "; ".join(details)
    text += f". Now: {preview_object(obj, heap)}"
    if name and shared:
        text += f". {', '.join(shared)} refer{'s' if len(shared) == 1 else ''} to the same object, so {'it sees' if len(shared) == 1 else 'they see'} this change too."
    return text


def _article(noun: str) -> str:
    return "an" if noun[:1] in "aeiou" else "a"


def _bracket(obj: dict, label: str) -> str:
    if obj["type"] == "instance":
        return f".{label}"
    if obj["type"] in ("set", "frozenset"):
        return label
    return f"[{label}]"


def _members_by_key(obj: dict) -> dict[str, dict]:
    from .diff import _keyed_members

    return _keyed_members(obj) or {}


def _member_desc(obj: dict, key: str, members: dict, heap: dict) -> str:
    value = members.get(key)
    label = member_label(obj, key)
    if obj["type"] in ("set", "frozenset"):
        return label
    return f"{_bracket(obj, label)} = {describe_value(value, heap, 30)}"


def exception_bullets(exc_type: str, message: str) -> list[str]:
    bullets = [f"Python raised {exc_type}: {message}" if message else f"Python raised {exc_type}."]
    hint = EXCEPTION_HINTS.get(exc_type)
    if hint:
        bullets.append(hint)
    return bullets
